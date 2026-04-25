"""WordPress post category labels (must match Posts → Categories on the site)."""

# Display order matches your site list; values are sent to XML-RPC as-is.
WORDPRESS_CATEGORY_CHOICES: tuple[tuple[str, str], ...] = (
    ("", "— Optional — use default from .env or Uncategorized"),
    ("Ansible", "Ansible"),
    ("AWS", "AWS"),
    ("Azure", "Azure"),
    ("Django", "Django"),
    ("GIT", "GIT"),
    ("Linux/Unix", "Linux/Unix"),
    ("MYSQL", "MYSQL"),
    ("Oracle", "Oracle"),
    ("PHP/MYSQL/Wordpress", "PHP/MYSQL/Wordpress"),
    ("POSTGRESQL", "POSTGRESQL"),
    ("Power-BI", "Power-BI"),
    ("Python/PySpark", "Python/PySpark"),
    ("RAC", "RAC"),
    ("rman-dataguard", "rman-dataguard"),
    ("shell", "shell"),
    ("SQL scripts", "SQL scripts"),
    ("SQL Server", "SQL Server"),
    ("Uncategorized", "Uncategorized"),
    ("Videos", "Videos"),
)
