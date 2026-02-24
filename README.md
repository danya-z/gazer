# Gazer
Gazer is a Terminal User Interface (TUI) application for querying PostgreSQL databases without explicitly writing SQL. The application enables lab members to construct database queries, by letting them use schema elements as building blocks.
The goal is to be able to construct queries by simply selecting the tables and columns of interest, selecting appropriate filters, and having the query built, sent out, and have results of said query ready in a .csv format in a matter of seconds.

Developed for the BDI Laboratory at Purdue University.

## Current Status

**Under active development.** Core functionality is implemented and working:
- ✅ Database connection to Purdue PostgreSQL server with authentication
- ✅ Schema fetching and caching
- ✅ Error handling with detailed diagnostics and clipboard support
- ✅ Query builder interface
- ✅ CSV export
- 🚧 CSV/MATLAB import (planned)
- 🚧 MATLAB export (planned)

## Installation

### Requirements

1. **Python 3.12+**

2. **pipx**
```bash
pip install pipx
pipx ensurepath
```

3. **VPN Access** - Gazer can only connect to the database if you are under Purdue's "Zone-network-clients" VPN.

4. **Database Credentials** - Your credentials must be recognized by the BDI lab's PostgreSQL server.

### Install Gazer
```bash
pipx install git+https://github.com/danya-z/gazer.git
```

### Update Gazer
```bash
pipx install git+https://github.com/danya-z/gazer.git --force
```

### Run
```bash
gazer
```

## Configuration

On first run, Gazer will prompt for your database username, which is saved in `~/.gazer/config.json` for subsequent sessions. Database passwords are never stored and must be entered each time.

## Known Issues

- Not tested on MacOS or Windows (Linux/WSL only)
- Gazer will attempt to fetch the schema and the foreign keys on every login. If it cannot fetch them, it will return an error, but will still allow you to send queries, just without automatic JOINs. That means that **most queries will not work**, unless you explicitly know how to construct them; and in that case, you should use dbeaver instead.
- Gazer expects a tree-like structure for the database. Automatic joining will crash if there are several ways to join two tables (e.g, if table A can join table D through either B or C, gazer will return an error).
