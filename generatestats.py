#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = "Julien Mousqueton"
__email__ = "julien.mousqueton_AT_computacenter.com"
__version__ = "1.0.0"

import pandas as pd
import logging 
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import warnings

warnings.warn("deprecated", DeprecationWarning)
warnings.filterwarnings("ignore")

logging.basicConfig(
    format='%(asctime)s,%(msecs)d %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO
)

# Define custom logging functions
def stdlog(msg):
    '''Standard info logging'''
    logging.info(msg)

def dbglog(msg):
    '''Debug logging'''
    logging.debug(msg)

def errlog(msg):
    '''Error logging'''
    logging.error(msg)

def load_data(file_path):
    # Load data from a JSON file and extract the nested 'statistiques'
    with open(file_path, 'r') as file:
        data = pd.read_json(file)
        df = pd.DataFrame(data['statistiques'].tolist())
        df['date'] = pd.to_datetime(df['date'])
        return df

def plot_cumulative_bar(df, output_file):
    # Creating a cumulative bar graph
    plt.figure(figsize=(12, 6))

    # Stacking bars for cumulative effect
    plt.bar(df['date'], df['Marche'], color='b', edgecolor='grey', label='Avis de Marché')
    plt.bar(df['date'], df['Modification'], bottom=df['Marche'], color='orange', edgecolor='grey', label='Modification')
    plt.bar(df['date'], df['Notification'], bottom=df['Marche'] + df['Modification'], color='g', edgecolor='grey', label="Avis d'attribution")

    # Adding titles and labels
    plt.title('Statistiques des avis')
    plt.xlabel('Date')
    plt.ylabel("Nombre d'avis")
    plt.xticks(df['date'], df['date'].dt.strftime('%Y-%m-%d'), rotation=45)
    plt.legend()
    plt.grid(False)
    plt.gca().yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    plt.tight_layout()

    # Save the plot as an image file
    plt.savefig(output_file)
    plt.close()

def main():
    # File path to your 'statistiques.json'
    file_path = 'statistiques.json'

    # File path for the output image
    output_file = 'statistiques.png'

    # Load the data
    stdlog('Chargement des données statistiques')
    df = load_data(file_path)

    # Plot the cumulative bar graph and save it as an image
    stdlog("Génération de l'image")
    plot_cumulative_bar(df, output_file)

if __name__ == "__main__":
    print('''
    ,---.    .---.    .--.           ,---.   
    | .-.\  / .-. )  / /\ \ |\    /| | .-.\  
    | |-' \ | | |(_)/ /__\ \|(\  / | | |-' ) 
    | |--. \| | | | |  __  |(_)\/  | | |--'  
    | |`-' /\ `-' / | |  |)|| \  / | | |     
    /( `--'  )---'  |_|  (_)| |\/| | /(      
   (__)    (_)              '-'  '-'(__) 
            par Julien Mousqueton          
    ''')
    main()
