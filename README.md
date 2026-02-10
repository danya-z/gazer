# Gazer
Gazer is a Terminal User Interface (TUI) application for querying PostgreSQL databases without explicitly writing SQL. The application enables lab members to construct database queries, by letting them use schema elements as building blocks.
The goal is to be able to construct queries by simply selecting the tables and columns of interest, selecting appropriate filters, and having the query built, sent out, and have results of said query ready in a .csv format in a matter of seconds.

Developed for the BDI Laboratory at Purdue University.

## Current Status

**Under active development.** Core functionality is implemented and working:
- ✅ Database connection to Purdue PostgreSQL server with authentication
- ✅ Schema fetching and caching
- ✅ Error handling with detailed diagnostics and clipboard support
- 🚧 Query builder interface (in progress)
- 🚧 CSV/MATLAB import and export (planned)

## Installation

### Requirements

1. **Poetry** - Dependency management tool
```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Or on Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

  Verify installation: `poetry --version`

2. **VPN Access** - Gazer can only connect to the database if you are under the Purdue's "Zone-network-clients" VPN.

3. **Database Credentials** - Your credentials must be recognized by the BDI lab's PostgreSQL server (TODO, add more specific instructions for new users).

### Install Gazer
```bash
# Clone the repository
git clone <repository-url>
cd gazer

# Install dependencies using Poetry
poetry install

# Run the application
poetry run gazer
```

## Configuration

On first run, Gazer will prompt for your database username, which is saved in ~/.gazer/config.json for subsequent sessions. Database passwords are never stored and must be entered each time.

## Known Issues

- Not tested on MacOS or Windows (Linux/WSL only)
- Gazer will attempt to fetch the schema and the foreign keys on every login. If it cannot fetch them, it will return an error, but will still allow you to send queries, just without automatic JOINs. That means that **most queries will not work**, unless you explicitly know how to construct them; and in that case, you should use dbeaver instead.
- Gazer expects a tree-like structure for the database. Automatic joining will crash if there are several ways to join two tables (e.g, if table A can join table D through either B or C, gazer will return an error).
