"""Mermaid diagram generation for schema visualization."""

from flaqes.core.schema_graph import SchemaGraph


def generate_mermaid_erd(graph: SchemaGraph) -> str:
    """Generate a Mermaid ERD diagram from a schema graph.
    
    Args:
        graph: The schema graph to visualize.
        
    Returns:
        Mermaid diagram syntax as a string.
    """
    lines = ["erDiagram"]
    lines.append("")
    
    # Add each table with its columns
    for table in graph:
        # Start table definition
        lines.append(f"    {table.name} {{")
        
        # Add columns
        for column in table.columns:
            # Sanitize type name (remove spaces, parentheses, brackets)
            col_type = column.data_type.raw.replace(" ", "_").replace("(", "").replace(")", "").replace("[", "").replace("]", "")
            
            # Sanitize column name
            col_name = column.name.replace(" ", "_")
            
            # Determine constraints
            constraints = []
            if table.primary_key and column.name in table.primary_key.columns:
                constraints.append("PK")
            if any(column.name in fk.columns for fk in table.foreign_keys):
                constraints.append("FK")
            
            # Add constraint suffix without quotes
            constraint_str = f" {','.join(constraints)}" if constraints else ""
            lines.append(f"        {col_type} {col_name}{constraint_str}")
        
        lines.append("    }")
        lines.append("")
    
    # Add relationships (foreign keys)
    for table in graph:
        for fk in table.foreign_keys:
            # Determine cardinality
            # Check if FK columns are nullable
            is_nullable = any(
                col.nullable 
                for col in table.columns 
                if col.name in fk.columns
            )
            
            # Mermaid ERD syntax: PARENT ||--o{ CHILD : "label"
            # ||--o{  : one parent to zero-or-more children (optional FK)
            # ||--|{  : one parent to one-or-more children (required FK)
            relationship = "||--o{" if is_nullable else "||--|{"
            
            # Format relationship
            label = f"{', '.join(fk.columns)}"
            lines.append(f"    {fk.target_table} {relationship} {table.name} : \"{label}\"")
    
    return "\n".join(lines)
