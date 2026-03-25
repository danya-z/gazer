# Gazer
Gazer is a Terminal User Interface (TUI) application for querying PostgreSQL databases without explicitly writing SQL. The application enables lab members to construct database queries, by letting them use schema elements as building blocks.
The goal is to be able to construct queries by simply selecting the tables and columns of interest, selecting appropriate filters, and having the query built, sent out, and have results of said query ready in a .csv format in a matter of seconds.

Developed for the BDI Laboratory at Purdue University.

## Current Status

**Under active development.** Core functionality is implemented and working:
-  Database connection to Purdue PostgreSQL server with authentication
-  Schema fetching and caching
-  Error handling with detailed diagnostics and clipboard support
-  Query builder interface
-  CSV export
-  CSV/MATLAB import (planned)
-  MATLAB export (planned)

## Installation

1. Installing **Python 3.12+**.

    Open your terminal and make sure you have python installed.
    For Windows, run
    ```bash
    python --version
    ```
    For MacOS or Linux run
    ```bash
    python3 --version
    ```
    If python is not installed, you will need to install it.
    More information about Python can be found on the official website
    https://python.org. 
    If you are installing python for Windows, make sure you check the 
    "Add to PATH" checkbox during installation.

2. Installing **git**.

    Make sure you have git installed by running
    ```bash
    git --version
    ```
    If git is not installed, you will need to install it.
    More information about git can be found on the official website
    https://git-scm.com/.

3. Installing **pipx**

    Ensure `pipx` is installed by running 
    ```bash
    pipx --version
    ```
    If it is not installed, you can do so via anaconda/pip/pip3.
    If you use anaconda, run
    ```bash
    conda install -c conda-forge pipx
    pipx ensurepath
    ```
    Otherwise, if you are on Windows, run
    ```bash
    python -m ensurepip --upgrade # This installs pip if it isn't installed already
    python -m pip install pipx
    python -m pipx ensurepath
    ```
    Otherwise, if you are on MacOS or Linux (or WSL), run
    ```bash
    python3 -m ensurepip --upgrade # This installs pip if it isn't installed already
    python3 -m pip install pipx
    python3 -m pipx ensurepath
    ```
    After you run `ensurepath`, restart (close and open) your terminal.

4. **Zone-network-clients VPN**. 

    Gazer _always_ requires you to be connected to the `Zone-network-clients` VPN. If you have never done so before, open [Cisco Secure Client](https://it.purdue.edu/services/vpn.php). Instead of using the dropdown select, enter 
    ```
    zonevpn.itap.purdue.edu/clients
    ```
    Select Connect, and authenticate with your Purdue career account credentials (you might have to use Duo for this). On future connections the dropdown for the Client should populate automatically. 

    Always connect to `Zone-network-clients` when using Gazer.

5. **Database Credentials**. 

    If you are a new lab member, your credentials might not be recognized by the BDI database. In that case, gazer will not be able to connect you to the db, and upon login will return something along the lines of 
    ```
    connection to server at "lpvdbapgdb02a.itap.purdue.edu" (172.26.133.49), port 5433 failed: FATAL:  no pg_hba.conf entry for host "172.30.1.245", user "username", database "bdidata", SSL encryption
    connection to server at "lpvdbapgdb02a.itap.purdue.edu" (172.26.133.49), port 5433 failed: FATAL:  no pg_hba.conf entry for host "172.30.1.245", user "username", database "bdidata", no encryption
    ```
    In that case request itap to add you to the `pg_hba.conf` file for the following database:
    ```
    server: lpvdbapgdb02a.itap.purdue.edu
    port: 5433
    name: bdidata
    ```
    If you need the access to the development database, request access to
    ```
    server: ldvdbapgdb02a.itap.purdue.edu
    port: 5433
    name: bdidata
    ```

6. Installing **Gazer**

    To install gazer, run
    ```bash
    git clone https://github.itap.purdue.edu/Nolte-Group/gazer.git ./gazer_install
    ```
    Git will clone Gazer from the group's private github;
    this will require you to authenticate with your Purdue credentials.
    After cloning succeeds, in the same directory you ran git clone, run pipx
    ```
    pipx install ./gazer_install --force
    ```
    Once Gazer is installed, test it by running
    ```bash
    gazer
    ```
    You can then delete the cloned `gazer_install` folder.

### Using gazer
If everything is set up properly, running `gazer` in your terminal will always launch Gazer. To connect to the database, don't forget to connect to the `Zone-network-clients` VPN.

### Update Gazer
Gazer does not update automatically. To update, delete the `gazer_install` folder if it still exists from a previous install, then run the install commands again:
```bash
git clone https://github.itap.purdue.edu/Nolte-Group/gazer.git ./gazer_install 
pipx install ./gazer_install --force
```
You can then delete the cloned `gazer_install` folder.

## Configuration

On first run, Gazer will prompt for your database username, which is saved in `~/.gazer/config.json` for subsequent sessions. Database passwords are never stored and must be entered each time. If, for whatever reason, you want to change the database server you are connecting to, you can do so by modifying `~/.gazer/config.json`. I strongly advise against that unless you are confident you know what you are doing.

## Known Issues

- Tested on Linux/WSL. Should work on Windows and MacOS but not extensively tested there
- Gazer will attempt to fetch the schema and the foreign keys on every login. If it cannot fetch them, it will return an error, but will still allow you to send queries, just without automatic JOINs. That means that **most queries will not work**, unless you explicitly know how to construct them; and in that case, you should use dbeaver instead.
- Gazer expects a tree-like structure for the database. Automatic joining will crash if there are several ways to join two tables (e.g, if table A can join table D through either B or C, gazer will return an error).
