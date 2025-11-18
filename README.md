# DSS-prototype-v1

## Setup Instructions

1. **Clone the repo:**
    ```
    git clone https://github.com/MarcoAnteghini/DSS-prototype-v1.git
    cd DSS-prototype-v1
    ```

2. **Create and activate conda environment:**
    ```
    conda env create -f environment.yml
    conda activate <your_env_name>   # see name in environment.yml, e.g. 'dss-prototype-v1'
    ```

3. **Set your OpenAI API key:**
    - Set it as an environment variable before running the app:
      ```
      export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxx"
      ```
    - **For persistent use:** add to your `.bashrc` or `.zshrc`, OR create an `.env` file (not committed!) and load it in Python.

4. **Run the app:**
    ```
    ./run.sh
    ```

## Environment

- All required dependencies are listed in `environment.yml`.

## Important
- **Do NOT commit your OpenAI key to the repo!**
- The `OPENAI_API_KEY` must be set before running `run.sh`.

