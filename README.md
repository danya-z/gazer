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

1. **Python 3.12+**.
More information about Python can be found on the official website
https://python.org

2. **pipx**.
Ensure `pipx` is installed with `pipx --version`. 
If it is not installed, you can install it via pip:
```bash
pip install pipx
pipx ensurepath
```
Alternatively, you can use anaconda:
```bash
conda install -c conda-forge pipx
pipx ensurepath
```

3. **VPN Access**. Gazer requires you to be connected to Purdue's `Zone-network-clients` VPN. If you have never done so before, open Cisco Secure Client (if you have never used Client, find the relevant information and the download link can be found [here](https://it.purdue.edu/services/vpn.php)). Instead of using the Client's dropdown select, manually enter `zonevpn.itap.purdue.edu/clients`. Select Connect, and authenticate using your Purdue career account credentials (you might have to use Duo for this). On future connections the dropdown for the Client should populate automatically -- then you can select `Zone-network-clients`.

4. **Database Credentials**. Your credentials must be recognized by the BDI database (the lab's PostgreSQL server).

### Install Gazer
```bash
pipx install git+https://github.com/danya-z/gazer.git
```

### Run
After you have connected to the `Zone-network-clients` VPN, run
```bash
gazer
```

### Update Gazer
Gazer does not update automatically. To update gazer, run
```bash
pipx install git+https://github.com/danya-z/gazer.git --force
```
This will not damage your config file; your saved username and defaults should not be overwritten by updates (they can, however, become obsolete).

## Configuration

On first run, Gazer will prompt for your database username, which is saved in `~/.gazer/config.json` for subsequent sessions. Database passwords are never stored and must be entered each time. If, for whatever reason, you want to change the database server you are connecting to, you can do so by modifying `~/.gazer/config.json`. I strongly advise against that unless you are confident you know what you are doing.

## Known Issues

- Not tested on MacOS or Windows (Linux/WSL only)
- Gazer will attempt to fetch the schema and the foreign keys on every login. If it cannot fetch them, it will return an error, but will still allow you to send queries, just without automatic JOINs. That means that **most queries will not work**, unless you explicitly know how to construct them; and in that case, you should use dbeaver instead.
- Gazer expects a tree-like structure for the database. Automatic joining will crash if there are several ways to join two tables (e.g, if table A can join table D through either B or C, gazer will return an error).
