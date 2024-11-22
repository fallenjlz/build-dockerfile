def backup_view_or_procedure(self, dataset, name, is_view):
    """Backup the definition of a view or procedure."""
    object_type = 'VIEW' if is_view else 'PROCEDURE'
    backup_dir = self.view_backup_dir if is_view else self.procedure_backup_dir
    backup_file = os.path.join(backup_dir, f"{dataset}_{name}.sql")

    if is_view:
        # Fetch the view definition from INFORMATION_SCHEMA.VIEWS
        query = f"""
        SELECT view_definition
        FROM `{self.tables[0]['project']}.{dataset}.INFORMATION_SCHEMA.VIEWS`
        WHERE table_name = '{name}';
        """
    else:
        # Fetch the procedure definition from INFORMATION_SCHEMA.ROUTINES
        query = f"""
        SELECT routine_definition
        FROM `{self.tables[0]['project']}.{dataset}.INFORMATION_SCHEMA.ROUTINES`
        WHERE routine_type = 'PROCEDURE' AND routine_name = '{name}';
        """

    print(f"Backing up {object_type}: {self.tables[0]['project']}.{dataset}.{name}")
    try:
        query_job = self.client.query(query)
        result = query_job.result()

        definition = None
        for row in result:
            definition = row[0]

        if not definition:
            raise ValueError(f"{object_type} {name} definition not found.")

        # Wrap view definition in CREATE OR REPLACE VIEW if it's a view
        if is_view:
            definition = f"CREATE OR REPLACE VIEW `{self.tables[0]['project']}.{dataset}.{name}` AS\n{definition}"
        # For procedures, prepend CREATE OR REPLACE PROCEDURE
        else:
            definition = f"CREATE OR REPLACE PROCEDURE `{self.tables[0]['project']}.{dataset}.{name}`()\n{definition}"

        # Save the definition to a backup file
        with open(backup_file, 'w') as file:
            file.write(definition)
        print(f"{object_type} definition backed up to {backup_file}")
    except Exception as e:
        print(f"Error backing up {object_type}: {e}")
        self.error_found = True