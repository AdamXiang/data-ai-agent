"""Low-level ETL building blocks used by the ETL analyst agent.

``ETLTools`` holds the plain Python/Pandas logic behind the LangChain
tools defined in ``agents/etl_analyst.py`` (``extract_load_tool`` and
``transform_load_tool``). Keeping this logic in a separate, tool-free
class makes it possible to unit test the extract/transform behavior
without spinning up an LLM or a LangGraph graph.

The three methods roughly map onto the "E", "T", and "L" of ETL:
    * ``extract_load``          -- Extract from an HTTP API, Load to disk.
    * ``transform_load_context`` -- Read a local file, return a preview
      of it so an LLM can write a transform for it.
    * ``execute_code``          -- Run the Pandas code the LLM wrote to
      actually perform the Transform + Load.
"""

import os

import pandas as pd
import requests


class ETLTools:
    """Container for the ETL agent's extract / transform / execute helpers.

    This class has no state of its own (``__init__`` takes no arguments)
    -- it exists purely to group related helper methods together and to
    give them a clean namespace when wrapped as LangChain tools.
    """

    def __init__(self):
        # No setup needed yet; kept as an explicit no-op constructor so
        # the class can gain instance state (e.g. a shared requests
        # session) later without changing how callers instantiate it.
        pass

    def extract_load(self, url: str, output_folder: str, format: str):
        """
        This tool extracts the data from the API (url) and loads it into the
        the desired location (output_folder).

        Args:
            url (str): The API endpoint from which to extract data.
            output_folder (str): The folder where the extracted data will be saved.
            format (str): The format in which to save the extracted data (csv, json, parquet).

        Returns:
            str: A message indicating the success or failure of the operation.

        """
        # Resolve output_folder (which may be a relative path like
        # "data/extract") against the project root, so this method works
        # the same way regardless of the current working directory the
        # script happens to be launched from.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        output_folder = os.path.join(project_root, output_folder)

        try:
            # Call the API and raise an exception for any 4xx/5xx response
            # instead of silently continuing with an error payload.
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            filename = os.path.join(output_folder, f"extracted_data.{format}")
            # Create the destination folder (and any missing parents) if
            # it doesn't already exist; exist_ok avoids an error on reruns.
            os.makedirs(output_folder, exist_ok=True)

            # NOTE: assumes the API response is a paginated payload with
            # the actual records under a "results" key (this matches
            # APIs like PokeAPI). Other APIs with a different shape would
            # need a different extraction here.
            df = pd.json_normalize(data["results"])
            if format == "csv":
                df.to_csv(filename, index=False)
            elif format == "json":
                df.to_json(filename, orient="records", lines=True)
            elif format == "parquet":
                df.to_parquet(filename, index=False)
            else:
                return f"Unsupported format: {format}"

            return f"Data successfully extracted and saved to {filename}"
        except requests.exceptions.RequestException as e:
            # Network errors, timeouts, and the raise_for_status() above
            # all land here; report failure as a string instead of
            # letting the LLM tool call raise, since LangChain tools are
            # expected to return text.
            return f"Failed to extract data: {e}"

    def transform_load_context(self, file_path: str):
        """
        This tool transforms the data from the specified file and loads it into the
        desired location (output_folder).

        Despite the docstring's mention of transforming/loading, this
        method itself does NOT transform or write any data -- it only
        *reads* the file and returns a small preview. That preview is fed
        into an LLM prompt (see ``transform_load_tool`` in
        ``agents/etl_analyst.py``) so the model can see real column names
        and sample values before it writes the actual Pandas
        transformation code, which is then run separately via
        ``execute_code``.

        Args:
            file_path (str): The path to the file containing the data to be transformed.
            output_folder (str): The folder where the transformed data will be saved.
            output_format (str): The format in which to save the transformed data (csv, json, parquet).
        Returns:
            str: A message indicating the success or failure of the operation.
        """
        # Pick the right Pandas reader based on the file extension so this
        # method can handle any of the formats extract_load can produce.
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension == ".csv":
            df = pd.read_csv(file_path)
        elif file_extension == ".json":
            df = pd.read_json(file_path, lines=True)
        elif file_extension == ".parquet":
            df = pd.read_parquet(file_path)
        else:
            return f"Unsupported file format: {file_extension}"

        # Only send a small preview (3 rows) to the LLM -- enough context
        # to infer column names/types without spending tokens on (or
        # leaking) the full dataset.
        top_3_rows = str(df.head(3))

        return top_3_rows

    def execute_code(self, code: str):
        """
        This tool executes the provided code and returns the output.

        Args:
            code (str): The code to be executed.
        Returns:
            str: The output of the executed code or an error message if execution fails.

        Warning:
            This runs ``code`` with Python's built-in ``exec()``, which
            executes the string with the full permissions of this process
            -- there is no sandboxing. ``code`` here is expected to be
            Pandas code generated by the LLM in ``transform_load_tool``,
            not arbitrary user input. Do not expose this method (or the
            ``transform_load_tool`` that calls it) to untrusted input
            without adding a sandbox or an allow-list first.
        """
        try:
            # Execute the LLM-generated Pandas code in-process. See the
            # Warning above -- this is intentionally simple for a
            # prototype, not production-hardened.
            exec(code)
            return "Code executed successfully."
        except Exception as e:
            # Catch broadly here because `code` is arbitrary and could
            # raise virtually any exception type; report it back to the
            # LLM as a string so it has a chance to retry/fix itself.
            return f"Failed to execute code: {e}"


if __name__ == "__main__":
    # Manual smoke test: preview a previously extracted CSV file directly,
    # without going through the LLM/agent layer.
    # NOTE: this path is hard-coded to one developer's machine -- update
    # it (or pass a path via sys.argv) before running this locally.
    obj = ETLTools()
    path = (
        "/Users/adamchang/Desktop/Side_Project/AI_Agent/data/extract/extracted_data.csv"
    )
    print(obj.transform_load_context(path))
