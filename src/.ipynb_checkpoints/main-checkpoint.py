#!/usr/bin/env python3
"""
BacDive Strain Search Interface - Corrected and Enhanced Version
This version integrates a highly detailed prompt with a correct schema and examples.
"""

import os
import io
import json
import logging
from datetime import datetime
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from SPARQLWrapper import SPARQLWrapper, JSON
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Secure API Key Handling ---
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logger.warning("OPENAI_API_KEY environment variable not set. Translation will fail.")

client = OpenAI(api_key=api_key)

# BacDive SPARQL Configuration
BACDIVE_ENDPOINT = "https://sparql.dsmz.de/api/bacdive"
last_results = pd.DataFrame()

def get_system_prompt():
    """
    Returns the detailed and correct system prompt based on the user's provided schema and examples.
    This is the most critical part for accurate query generation.
    """
    return """
    You are an expert SPARQL query generator for the BacDive database. 
    Convert the human query into a valid SPARQL query for the BacDive SPARQL endpoint.

    ### IMPORTANT PREFIXES (Always include these):
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX d3o: <https://purl.dsmz.de/schema/>
    PREFIX bd: <https://purl.dsmz.de/bacdive/>

    ### CORE SCHEMA (DSMZ Digital Diversity Ontology - D3O):
    The main entity is `d3o:Strain`. Most other information is linked to a strain via an intermediate object that uses the `d3o:describesStrain` property.

    **Key Classes and Properties:**
    - **d3o:Strain**: The central class for a strain.
      - `rdfs:label`: The strain's name (e.g., "Bacillus subtilis DSM 10").
      - `d3o:hasGenus`, `d3o:hasSpecies`, `d3o:hasFamily`, `d3o:hasOrder`, `d3o:hasClass`, `d3o:hasPhylum`, `d3o:hasDomain`: Taxonomic ranks.
      - `d3o:isTypeStrain`: A boolean (`true`/`false`) indicating if it's a type strain.
      - `d3o:hasBacDiveID`: The numerical ID for the strain.

    - **d3o:LocationOfOrigin**: Describes where the strain was found.
      - `d3o:describesStrain`: Links this information to a `d3o:Strain`.
      - `d3o:hasCountry`: The country of origin (e.g., "Germany").
      - `d3o:hasLocation`: A more specific location (e.g., "Black Forest soil").

    - **d3o:IsolationSource**: The source material.
      - `d3o:describesStrain`: Links this to a `d3o:Strain`.
      - `rdfs:label`: The name of the source (e.g., "soil", "marine sediment").

    - **d3o:CultureTemperature**: Growth temperature conditions.
        - `d3o:describesStrain`: Links to a `d3o:Strain`.
        - `d3o:hasTemperatureRangeEnd` or `d3o:hasTemperatureRangeStart`: Numerical values for filtering.

    - **Other Important Classes**: `d3o:GramStain`, `d3o:CellMotility`, `d3o:OxygenTolerance`, `d3o:Enzyme`.

    ### QUERY EXAMPLES:

    **1. Get the full taxonomy of all strains:**
    ```sparql
    PREFIX rdfs: [http://www.w3.org/2000/01/rdf-schema#](http://www.w3.org/2000/01/rdf-schema#)
    PREFIX d3o: [https://purl.dsmz.de/schema/](https://purl.dsmz.de/schema/)
    PREFIX bd: [https://purl.dsmz.de/bacdive/](https://purl.dsmz.de/bacdive/)

    SELECT ?strain ?domain ?phylum ?class ?order ?family ?genus ?species
    WHERE {
      ?strain a d3o:Strain;
              d3o:hasDomain ?domain;
              d3o:hasPhylum ?phylum;
              d3o:hasClass ?class;
              d3o:hasOrder ?order;
              d3o:hasFamily ?family;
              d3o:hasGenus ?genus;
              d3o:hasSpecies ?species.
    }
    LIMIT 100
    ```

    **2. Find all data linked to a specific strain ID (e.g., 159796):**
    ```sparql
    PREFIX rdfs: [http://www.w3.org/2000/01/rdf-schema#](http://www.w3.org/2000/01/rdf-schema#)
    PREFIX d3o: [https://purl.dsmz.de/schema/](https://purl.dsmz.de/schema/)
    PREFIX bd: [https://purl.dsmz.de/bacdive/](https://purl.dsmz.de/bacdive/)

    SELECT ?type ?predicate ?label 
    WHERE {
        ?obj a ?type ;
             d3o:describesStrain [https://purl.dsmz.de/bacdive/strain/159796](https://purl.dsmz.de/bacdive/strain/159796) ;
             ?predicate ?label .
    }
    ```

    ### INSTRUCTIONS:
    - ALWAYS use the prefixes provided. Notice that the ontology prefix is `d3o:`.
    - Use `FILTER` with `CONTAINS(LCASE(?variable), "search term")` for flexible text matching.
    - Always include a `LIMIT` clause (e.g., `LIMIT 100`) to keep results manageable.
    - Return ONLY the complete SPARQL query without any explanations or additional text.
    """

def translate_to_sparql(natural_query):
    """Translates natural language to SPARQL using the OpenAI API."""
    if not client.api_key:
        return "# Error: OPENAI_API_KEY is not configured. Please set it in run.sh."
    try:
        system_prompt = get_system_prompt()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": natural_query}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        sparql_query = response.choices[0].message.content.strip()
        # Clean up markdown formatting just in case
        sparql_query = sparql_query.replace("```sparql", "").replace("```", "").strip()
        logger.info(f"Successfully translated query: {natural_query[:50]}...")
        return sparql_query
    except Exception as e:
        logger.error(f"Error in OpenAI translation: {e}", exc_info=True)
        return f'# Error generating SPARQL query: {str(e)}'

def execute_sparql_query(query):
    """Executes a SPARQL query against the BacDive endpoint."""
    if query.startswith("# Error"):
        return {"error": "Translation failed, cannot execute query."}
    try:
        logger.info("Attempting to execute SPARQL query...")
        sparql = SPARQLWrapper(BACDIVE_ENDPOINT)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        sparql.setTimeout(30)
        results = sparql.query().convert()
        logger.info("SPARQL query executed successfully.")
        return results
    except Exception as e:
        logger.warning(f"SPARQL execution failed: {e}")
        return {"error": f"BacDive endpoint error: {str(e)}"}

def results_to_dataframe(results):
    """Converts SPARQL JSON results to a pandas DataFrame."""
    if "error" in results:
        return pd.DataFrame([{"Message": "Query execution failed.", "Error": results["error"]}])
    bindings = results.get("results", {}).get("bindings", [])
    if not bindings:
        return pd.DataFrame([{"Message": "Query executed successfully but returned no results."}])
    data = [{k: v["value"] for k, v in b.items()} for b in bindings]
    df = pd.DataFrame(data)
    logger.info(f"Converted results to DataFrame with {len(df)} rows.")
    return df

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/translate_query', methods=['POST'])
def translate_query_route():
    global last_results
    try:
        natural_query = request.get_json().get('query', '').strip()
        if not natural_query:
            return jsonify({"error": "No query provided"}), 400

        logger.info(f"Processing query: {natural_query}")
        
        sparql_query = translate_to_sparql(natural_query)
        results = execute_sparql_query(sparql_query)
        df = results_to_dataframe(results)
        last_results = df
        
        return jsonify({
            "sparql_query": sparql_query,
            "results": df.to_dict('records'),
            "endpoint_accessible": "error" not in results
        })
    except Exception as e:
        logger.error(f"Critical error in translate_query route: {e}", exc_info=True)
        return jsonify({"error": f"A critical server error occurred: {e}"}), 500

@app.route('/download_csv')
def download_csv():
    global last_results
    if last_results.empty:
        return "No results available for download", 404
    output = io.BytesIO()
    last_results.to_csv(output, index=False, encoding='utf-8')
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='bacdive_results.csv')

@app.route('/example_queries')
def example_queries():
    examples = [
        "get taxonomy of all strains",
        "Give me all strains isolated from soil in Germany",
        "Find all data for strain 159796"
    ]
    return jsonify({"examples": examples})

if __name__ == '__main__':
    logger.info("🔬 Starting BacDive Interface - Enhanced Prompt Version")
    app.run(debug=True, host='0.0.0.0', port=5001)

