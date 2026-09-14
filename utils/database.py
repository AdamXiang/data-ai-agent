import psycopg2


class Database:
    """Thin wrapper around a PostgreSQL connection used to inspect database schemas.

    The class opens (or attempts to open) a connection to a PostgreSQL
    database from ``psycopg2.connect`` keyword arguments, and exposes helpers
    that turn database metadata into plain-text descriptions. These
    descriptions can later be embedded into prompts, for example to give an
    LLM-based agent the full picture of a schema.

    Attributes:
        db_config (dict): The keyword arguments used to open the connection
            (e.g. ``host``, ``port``, ``database``, ``user``, ``password``).
        connection (psycopg2.extensions.connection | None): The live database
            connection, or ``None`` when the initial connection attempt failed.
    """

    def __init__(self, db_config):
        """Initialize the wrapper and try to connect to PostgreSQL.

        Args:
            db_config (dict): Keyword arguments accepted by
                ``psycopg2.connect``, e.g. ``host``, ``port``, ``database``,
                ``user`` and ``password``.

        Note:
            A failed connection attempt does not raise an exception. Instead,
            an error message is printed and ``self.connection`` is set to
            ``None`` so callers can check the connection status explicitly.
        """
        # Keep the raw configuration so the connection could later be
        # re-opened or inspected without re-passing the settings
        self.db_config = db_config

        try:
            # Open the database connection using the supplied configuration
            self.connection = psycopg2.connect(**db_config)
        except psycopg2.Error as e:
            # Connection failed -- report it and leave a sentinel for callers
            print(f"Error connecting to the database: {e}")
            self.connection = None

    def get_schema_details(self, schema_name):
        """Build a textual description of a database schema and its data.

        For every table found in the given schema, the description records the
        table name, the name and data type of each column, and up to five
        sample rows taken from that table.

        Args:
            schema_name (str): The name of the schema to inspect,
                e.g. ``"public"``.

        Returns:
            str | None: A multi-line, human-readable summary of the schema,
            or ``None`` when there is no active database connection.
        """
        # Accumulator that receives every line of the generated description
        schema_info_content = ""

        # Bail out early when there is no live connection to query
        if not self.connection:
            print("No database connection.")
            return

        try:
            # The cursor is scoped to this block and closed automatically
            # when the ``with`` statement exits
            with self.connection.cursor() as cursor:
                schema_info_content = f"Database Schema: {schema_name}\n"

                # List every table that belongs to the requested schema
                cursor.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s;
                    """,
                    # Parameterized query: the schema name is passed as a
                    # placeholder value rather than embedded in the SQL text,
                    # which guards against SQL injection
                    (schema_name,),
                )
                # fetchall() returns a list of single-element tuples,
                # e.g. [('users',), ('orders',), ('products',)]
                tables = (
                    cursor.fetchall()
                )

                for table in tables:
                    table_name = table[0]
                    schema_info_content += f"\nTable: {table_name}\n"

                    # Fetch the name and data type of every column in the
                    # current table, again using a parameterized query
                    cursor.execute(
                        """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s;
                        """,
                        (schema_name, table_name),
                    )
                    columns = cursor.fetchall()

                    for column in columns:
                        column_name, data_type = column
                        schema_info_content += (
                            f"  Column: {column_name}, Data Type: {data_type}\n"
                        )

                    # Pull a small sample of real rows so the description shows
                    # concrete values. The table name comes from PostgreSQL's
                    # own information_schema query above, so interpolating it
                    # into the SQL text is safe here
                    cursor.execute(
                        f"""
                        SELECT * 
                        FROM {schema_name}.{table_name}
                        LIMIT 5;
                        """
                    )
                    sample_data = cursor.fetchall()
                    schema_info_content += "  Sample Data:\n"

                    for row in sample_data:
                        schema_info_content += f"    {row}\n"

        except psycopg2.Error as e:
            # Report failures (e.g. permission errors) while keeping any
            # partial description already accumulated
            print(f"Error fetching schema details: {e}")

        return schema_info_content
