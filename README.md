Line configuration management

aka. Machine Configuration Database

see: https://confluence.slac.stanford.edu/display/PCDS/Validated+Machine+Configuration+Database+System 


### Install Steps

- Create the conda environment from the base directory
    - `conda env create -f environment.yml`
- Activate the conda environment by name(see .yml file for correct name)
    - `conda activate mcd_0_0_1`
- Install flask_authnz submodule
    - Update and activate submodule
    - `cd $HOME/licco`
    - `git submodule init`
    - `git submodule update`
- Install javascript packages from within react folder
    - `cd react`
    - `npm install` OR copy over a node_modules folder installed on a machine with the same build requirements
- Start front end REACT development server 
    - `npm run dev`
- Run backend in debug mode with gunicorn server in another terminal/session
    - `python3 -m gunicorn --env LICCO_CONFIG="./config.ini" start:app`


## Configuration

See `config.ini` file for available options.