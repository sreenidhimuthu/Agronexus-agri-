# database.py
# This file is used to import and re-export the database instance
# from models.py to avoid circular imports

from models import db

# This allows you to import db from database.py instead of models.py
# Usage in other files: from database import db