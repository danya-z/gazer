# Gazer
Gazer is a Terminal User Interface (TUI) application for querying PostgreSQL databases without explicitly writing SQL. The application enables lab members to construct database queries, by letting them use schema elements as building blocks.
The goal is to be able to construct queries by simply selecting the tables and columns of interest, selecting appropriate filters, and having the query built, sent out, and have results of said query ready in a .csv format in a matter of seconds.

Developed for the BDI Laboratory at Purdue University.

## Current Status

**Under active development.** Core functionality is implemented and working:
-  Database connection to Purdue PostgreSQL server with authentication
-  Schema fetching, caching, manual cache clears
-  Error handling with diagnostics and clipboard support
-  Query builder interface
-  Query parsing and automatic linking
-  CSV export
-  CSV/MATLAB import (planned)
-  MATLAB export (planned)

## Installation
    
0. **The WHAT and the WHY**

    Read this if you want to understand the process behind the installation procedure.

    Gazer is a python package and it depends on other projects and libraries.
    This makes it cumbersome to compile into a simple executable file you could directly download.
    For that reason, Gazer should be installed via a python "package manager".

    You might have heard of pip, which is the python's default package manager. 
    It is is great, but it lacks functionality when it comes to managing apps like Gazer.
    By default pip installs dependencies globaly on your system, which can cause version conflicts among apps.

    For that reason, Gazer uses pipx — a tool that installs apps in isolated environments, 
    making sure that they don't conflict with each other or your system.
    Pipx handles dependency hell automatically, so you don't have to think about it.

1. **Installing Python 3.12+**.

    On your computer, python can run under the alias `python` or `python3`;
    check which alias is relevant to you, by running the following commands in your terminal:
    ```bash
    python3 --version
    python --version
    ```
    Make sure at least one of the commands works and returns a version 3.12. 
    README will refer to the `python` command; replace it with `python3` if that alias works for you instead.

    If both `python` and `python3` returned an error, you will have to install Python.
    More information about Python can be found on the official website
    https://python.org. If you proceed with installing python for Windows, 
    make sure you check the "**Add to PATH**" checkbox during installation.

2. **Installing pip**.
    
    Ensure that pip is installed by running 
    ```bash
    python -m ensurepip --upgrade
    ```
    After you run the command, you should see pip either installing, updating, or notifying that "requirement is already satisfied".

    If the command returns an error, you might have `ensurepip` patched out of your installation (some distributors just do that for some reason).
    Check the [pip documentation](https://pypi.org/project/pip/) for the installation procedures.

3. **Installing git**.

    Make sure you have git installed by running
    ```bash
    git --version
    ```
    If git is not installed, you will need to install it.
    More information about git can be found on the [official website](https://git-scm.com/).

4. **Installing pipx**.

    Ensure `pipx` is installed by running 
    ```bash
    pipx --version
    ```
    If it is not installed, run
    ```bash
    python -m pip install pipx
    python -m pipx ensurepath
    ```
    After you run `ensurepath`, restart (close and open) your terminal.

5. **Zone-network-clients VPN**. 

    Gazer _always_ requires you to be connected to the `Zone-network-clients` VPN. If you have never done so before, open [Cisco Secure Client](https://it.purdue.edu/services/vpn.php). Instead of using the dropdown select, enter 
    ```
    zonevpn.itap.purdue.edu/clients
    ```
    Select Connect, and authenticate with your Purdue career account credentials (you might have to use Duo for this). On future connections the dropdown for the Client should populate automatically. 

    Always connect to `Zone-network-clients` when using Gazer.

6. **Database Credentials**. 

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

7. **Installing Gazer**.

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

### Installing with conda (not recommended)

If you already use conda and prefer it over pipx, you can install Gazer into a conda environment instead. To do so, clone the repository (step 7) and run:
```bash
conda create -n gazer python=3.12
conda activate gazer
pip install ./gazer_install
```
Note that with conda, you will need to run `conda activate gazer` every time you open a new terminal before you can use the `gazer` command.

## Using gazer

If everything is set up properly, running `gazer` in your terminal will always launch Gazer. 
To connect to the database, don't forget to always connect to the `Zone-network-clients` VPN first.

## Updating Gazer

Gazer does not update automatically. Whenever you want to update it, run 
```bash
gazer --update
```

## Configuration

On first run, Gazer will prompt for your database username, which is saved in `~/.gazer/config.json` for subsequent sessions. Database passwords are never stored and must be entered each time. If, for whatever reason, you want to change the database server you are connecting to, you can do so by modifying `~/.gazer/config.json`. I strongly advise against that unless you are confident you know what you are doing.

## Known Issues

- Tested on Linux/WSL. Should work on Windows and MacOS but not extensively tested there
- Gazer will attempt to fetch the schema and the foreign keys on every login. If it cannot fetch them, it will return an error, but will still allow you to send queries, just without automatic JOINs. That means that **most queries will not work**, unless you explicitly know how to construct them; and in that case, you should use dbeaver instead.
- Gazer expects a tree-like structure for the database. Automatic joining will crash if there are several ways to join two tables (e.g, if table A can join table D through either B or C, gazer will return an error).

