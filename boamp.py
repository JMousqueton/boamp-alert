#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = "Julien Mousqueton"
__email__ = "julien.mousqueton_AT_computacenter.com"
__version__ = "1.0.1"

# Import for necessary Python modules
import requests
import json 
import pymsteams # To Publish Card on teams 
from datetime import datetime, timedelta
import logging 
import argparse
import re # For  removing HTML tag in debug mode 

# For checking python version
import sys

#For reading .env 
import os 
from dotenv import load_dotenv

# Configure logging
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

# Remove HTML Code from message in debug mode  
def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def fetch_boamp_data(date, select_option=None):
    """
    Fetches data from the BOAMP API for a given date.
    :param date: A string representing the date in the format 'yyyy-MM-dd'.
    :param attribution_only: A boolean indicating whether to filter for attribution announcements only.
    :return: JSON response data.
    """
    year, month, day = date.split('-')
    search = "date_format(dateparution, 'yyyy') = '" + year + "' and date_format(dateparution, 'MM') = '"+month+"' and date_format(dateparution, 'dd') = '"+day+"' and (descripteur_libelle like 'Informatique%' " 
    for word in descripteurs_list:
        search += " or descripteur_libelle = '"+word+"'" 
    search += ")"
    if select_option == 'attribution':
        search += " and nature='ATTRIBUTION'"
        stdlog('(!) Seulement les attributions')
    elif select_option == 'ao':
        search += " and nature='APPEL_OFFRE'"
        stdlog("(!) Seulement les Appels d'Offre")
    elif select_option == 'rectificatif':
        search += " and nature='RECTIFICATIF'"
        stdlog("(!) Seulement les rectificatifs d'appels d'offre")
    
    url = "https://www.boamp.fr/api/explore/v2.1/catalog/datasets/boamp/records"
    params = {
        "select": "*",
        "where": f"{search}",
        "limit": 99,
        "offset": 0,
        "timezone": "UTC",
        "include_links": "false",
        "include_app_metas": "false"
    }
    if debug_mode:
        stdlog('API : '+ url+'?select=*&where='+search)
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"Other Error: {err}")

def determine_status(nature):
    """
    Determines the status based on the nature field.
    :param nature: The nature field from the record.
    :param record: The entire record from the response.
    :return: The determined status.
    """
    match nature:
        case "APPEL_OFFRE":
            status = "🟢"
        case "RECTIFICATIF":
            status = "🟠"
        case "R\u00e9sultat de march\u00e9":   # Vérifier la pertinence 
            status = "🏆"
        case "ATTRIBUTION":
            status = "🏆"
        case _:
            status = "Non disponible"
    return status

# Send message to Teams Channel regarding the nature of the message 
def tomsteeams(nature,title,message):
    if nature == "ATTRIBUTION":
        webhook = webhook_attribution
    else:
        webhook = webhook_marche
    # Create a connector card object
    myTeamsMessage = pymsteams.connectorcard(webhook)
    # Prepare card object 
    myTeamsMessage.text(message)              
    myTeamsMessage.title(title)
    # Send the message
    try:
        myTeamsMessage.send()
    except pymsteams.TeamsWebhookException as e:
        print(f"Erreur à l'envoie du message MSTeams : {e}")


def parse_boamp_data(api_response, date):
    """
    Parses the JSON response from the BOAMP API and extracts key information.
    :param api_response: JSON response data from the BOAMP API.
    :param date: Date string used for the filename.
    """
    total_count = api_response.get('total_count', 0)
    if total_count == 0:
        stdlog('Pas de nouvel avis pour ' + date)
        return
      
    stdlog(str(total_count) + ' enregistrement(s) récupéré(s)')
    i=0 
    # Write the response to a file
    filename = f"data/boamp-{date}.json"
    stdlog('Ecriture du fichier ' +  filename)
    try:
        with open(filename, 'w') as file:
            json.dump(api_response, file, indent=4)
    except TypeError as e:
        errlog(f"Error in JSON serialization: {e}")
    except IOError as e:
        errlog(f"File I/O error: {e}")


    if total_count > 99:
        stdlog("Plus de 100 résultats !!!")
    stdlog('Extraction des données ...')
    if 'results' in api_response and api_response['results']:
        for record in api_response['results']:
            
            """
            Grab all data in variable  
            """
            nature = record.get('nature')
            status = determine_status(nature)
            ID = record.get('idweb', 'Non disponible')
            acheteur = record.get('nomacheteur', 'Non disponible')
            objet = record.get('objet', 'Non disponible')
            services = record.get('descripteur_libelle')
            services_clean = ', '.join(services)
            services_list= services_clean.replace('Informatique (','').replace(')','')
            
            pubdate =  record.get('dateparution', 'Non disponible')
             
            typemarche = record.get('famille_libelle', 'Non disponible')
            devise = ''
            try:
                titulaires_list = record.get('titulaire',[])
                # Check if the list has only one entry or multiple entries
                if len(titulaires_list) == 1:
                    # If there's only one entry, just take that entry
                    titulaires = titulaires_list[0]
                else:
                    # If there are multiple entries, join them with ', '
                    titulaires = ', '.join(titulaires_list)
            except:
                titulaires = ''
            deadline = record.get('datelimitereponse', 'Non disponible')
            try:
                date_object = datetime.fromisoformat(deadline)
                deadline = date_object.strftime("%Y-%m-%d")
            except:
                pass
            

            ## Attaque des données JSON du champs donnees
            donnees_brut = record.get('donnees',{})
            donnees = json.loads(donnees_brut)

            if not titulaires:
                try:
                    titulaires_list= donnees['ATTRIBUTION']['DECISION']['TITULAIRE']
                    if isinstance(titulaires_list, list):
                        nb=len(titulaires_list)
                        for titulaire in titulaires_list:
                            nb = nb - 1
                            titulaires += titulaire['DENOMINATION']
                            if nb > 0:
                                titulaires += ', '
                    else:
                        titulaires = titulaires_list['DENOMINATION']
                except:
                    titulaires = ''
            if not deadline:
                try:
                    deadline = donnees['CONDITION_DELAI']['RECEPT_OFFRES']
                    date_object = datetime.fromisoformat(deadline)
                    deadline = date_object.strftime("%Y-%m-%d")
                except:
                    deadline = ''
            if deadline:
                target_date = datetime.strptime(deadline, "%Y-%m-%d")
                current_date = datetime.now()
                delai = (target_date - current_date).days
            try:
                devisetotal = donnees['OBJET']['CARACTERISTIQUES']['VALEUR_TOTALE']['@DEVISE']
                montanttotal = donnees['OBJET']['CARACTERISTIQUES']['VALEUR_TOTALE']['#text']
            except:
                devisetotal = ''
                montanttotal = ''
            try:
                ref = donnees['CONDITION_ADMINISTRATIVE']['REFERENCE_MARCHE']
            except:
                ref = '' 
            if not ref:
                try:
                    ref = donnees['OBJET']['REF_MARCHE']
                except:
                    ref = ''
            try:
                devise = donnees['OBJET']['CARACTERISTIQUES']['VALEUR']['@DEVISE']
                valeur = donnees['OBJET']['CARACTERISTIQUES']['VALEUR']['#text']
            except:
                 devise = ''
                 valeur = ''
            try:
                duree = donnees.get('OBJET', {}).get('DUREE_DELAI', {}).get('DUREE_MOIS', '')
            except:
                duree = ''
            try:
                offresrecues = donnees.get('ATTRIBUTION', {}).get('DECISION', {}).get('RENSEIGNEMENT', {}).get('NB_OFFRE_RECU', '')
            except:
                offresrecues = ''
            try:
                if 'DIV_EN_LOTS' in donnees['OBJET'] and 'OUI' in donnees['OBJET']['DIV_EN_LOTS']:
                    lots = True 
                else:
                    lots = False 
            except KeyError:
                    lots = False
            if lots:
                lots_data = donnees['OBJET'].get('LOTS', {}).get('LOT', [])
                nblots = len(lots_data)            
            try: 
                annonce_lie = record.get('annonce_lie', [])
            except: 
                annonce_lie = ''
            urlavis = record.get('url_avis', 'Not available')

            

            message=''

            # Create the message for msteams card 
            if pubdate:
                message='<strong>' + pubdate + '</strong>\n\n'
            message += '<strong>Acheteur : </strong>' + acheteur + '\n\n'
            if ref:
                message += '<strong>Référence marché : </strong>' + ref + '\n\n'
            message += '<strong>Services : </strong>' + services_list + '\n\n'
            if typemarche == "Marchés entre 90 k€ et seuils européens" and seuilmarches: 
                typemarche = typemarche.replace('seuils européens',seuilmarches)
            message += '<strong>Type de marché : </strong>' + typemarche + '\n\n' 
            if valeur:
                message += '<strong>Valeur du marché : </strong>' + valeur + ' ' + devise + '\n\n'
            elif montanttotal:
                message += '<strong>Valeur du marché : </strong>' + montanttotal + ' ' + devisetotal + '\n\n'
            if lots:
                message += '<strong>Marché alloti : </strong>✅\n\n'
                try: 
                    for lot in lots_data:
                        intitule = lot.get('INTITULE','')
                        if not intitule:
                            intitule = lot.get('DESCRIPTION')
                        num = lot.get('NUM')
                        info = lot.get('INFO_COMPL','')
                        deviselot = lot.get('VALEUR',{}).get('@DEVISE','')
                        montantlot = lot.get('VALEUR',{}).get('#text','')
                        if not num:
                            message += '\t' + intitule + '\n\n' 
                        else:   
                            message += '\tLot '+ num + " : " +  intitule + '\n\n'
                        if montantlot:
                            message += '\t\tValeur du lot : ' + montantlot + ' ' + deviselot + '\n\n'
                        message += '\t\t'+info+'\n\n'
                except: 
                    pass
                    #Parsing error should be investigate (ie 2023-12-23)
            if deadline:
                message += '<strong>Deadline : </strong>' + deadline + ' ('+ str(delai)+ ' jours)\n\n' 
            if offresrecues:
                message += '<strong>Offre(s) reçue(s) : </strong>' + offresrecues + '\n\n'
            if titulaires:
                message += '<strong>Titulaire(s) : </strong>' + titulaires + '\n\n'
            if duree:
                message +='<strong>Durée du marché (en mois) : </strong>' + duree + '\n\n'
            if annonce_lie:
                annonce_lie_list= ', '.join(annonce_lie)
                message += '<strong>Annonce(s) liée(s) : </strong>' + annonce_lie_list + '\n\n'
            message += '<strong>Avis : </strong>: ' + urlavis + '\n\n'
            
            # Add a title to the message
            title = '['+ID+'] ' + status + '  ' + objet
            # Send MsTeams Card
            if not debug_mode:
                tomsteeams(nature,title,message)
                i+=1 
            else:
                print(title + '\n' + remove_html_tags(message.replace('\n\n','\n')))
                print('-----------------------------------------------')
            
    else:
        errlog("No results found")

    stdlog(str(i) + ' message(s) envoyé(s) dans msteams')


if __name__ == "__main__":
    print('''
    ,---.    .---.    .--.           ,---.   
    | .-.\  / .-. )  / /\ \ |\    /| | .-.\  
    | |-' \ | | |(_)/ /__\ \|(\  / | | |-' ) 
    | |--. \| | | | |  __  |(_)\/  | | |--'  
    | |`-' /\ `-' / | |  |)|| \  / | | |     
    /( `--'  )---'  |_|  (_)| |\/| | /(      
    (__)     (_)             '-'  '-'(__) 
            par Julien Mousqueton / Computacenter         
        ''')
    
    if sys.version_info < (3, 10):
        stdlog("Python version is below 3.10. You need Python 3.10 or higher to use the match function.")
        exit(1)


    # Setup argument parser
    parser = argparse.ArgumentParser(description="Script to fetch and process BOAMP data")
    parser.add_argument("-D", "--debug", action="store_true", help="Active le mode debug (aucun message ne sera envoyé à msteams)")
    parser.add_argument("-n", "--now", action="store_true", help="Force la date du jour au lieu de J-1")
    parser.add_argument("-d", "--date", type=str, help="Spécifie la date du scan au format yyyy-mm-dd", metavar="YYYY-MM-DD")
    parser.add_argument("-s", "--select", type=str, choices=['attribution', 'ao', 'rectificatif'], help="Selection de la nature de l'avis : 'attribution', 'rectificatif' ou 'ao' (Appel d'Offre)")

    # Parse arguments
    args = parser.parse_args()

    # Main script execution
    debug_mode=args.debug
    today_mode=args.now
    specified_date = args.date
    select_option = args.select 

    if debug_mode:
        stdlog("DEBUG MODE")

    # Load the .env file
    load_dotenv()

    # Use environment variables
    webhook_marche = os.getenv('WEBHOOK_MARCHE')
    webhook_attribution = os.getenv('WEBHOOK_ATTRIBUTION')

    ## Get Keywords 
    descripteurs_list = os.getenv('DESCRIPTEURS', '').split(',')
    if debug_mode:
        stdlog('DESCRIPTEURS : ' + os.getenv('DESCRIPTEURS', ''))

    seuilmarches = os.getenv('SEUILMARCHES','')


    if not webhook_marche or not webhook_attribution:
        errlog("Erreur: Au moins une des deux webhook URLs est manquante ou vide.")
        exit(1)

    # Determine the date to process
    if today_mode:
        date_to_process = datetime.now().strftime("%Y-%m-%d")
        stdlog("(!) TODAY MODE")
    elif specified_date:
        date_to_process = specified_date
        stdlog("(!) FORCED DATE MODE")
    else:
        # Calculate yesterday's date
        yesterday = datetime.now() - timedelta(days=1)
        date_to_process = yesterday.strftime("%Y-%m-%d")

    stdlog('Récuperation des données du BOAMP pour le ' + date_to_process)
    data = fetch_boamp_data(date_to_process, select_option)
    if data:
        stdlog('Analyse des données du BOAMP pour le ' + date_to_process)
        parse_boamp_data(data, date_to_process)
    else:
        errlog('Pas de donnée à analyser')

    stdlog('Fini !')