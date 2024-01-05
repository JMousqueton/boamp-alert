import requests
import json
import pymsteams
from datetime import datetime, timedelta
import logging
import argparse
import re


#For Webhook 
import os
from dotenv import load_dotenv

descripteur_list = os.getenv('DESCRIPTEURS', '').split(',')

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

def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def fetch_boamp_data(date):
    """
    Fetches data from the BOAMP API for a given date.
    :param date: A string representing the date in the format 'yyyy-MM-dd'.
    :return: JSON response data.
    """
    year, month, day = date.split('-')
    search = "date_format(dateparution, 'yyyy') = '" + year + "' and date_format(dateparution, 'MM') = '"+month+"' and date_format(dateparution, 'dd') = '"+day+"' and (descripteur_libelle like 'Informatique%' " 
    for word in descripteur_list:
        search += " or descripteur_libelle = '"+word+"'" 
    search += ")"
    url = "https://www.boamp.fr/api/explore/v2.1/catalog/datasets/boamp/records"
    params = {
        "select": "*",
        "where": f"{search}"
    }

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
        case "R\u00e9sultat de march\u00e9":
            status = "🏆"
        case "ATTRIBUTION":
            status = "🏆"
        case _:
            status = "Non disponible"
    return status

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
        # myTeamsMessage.send()
        print('SENT !!!!')
    except pymsteams.TeamsWebhookException as e:
        print(f"Erreur à l'envoie du message MSTeams : {e}")


def parse_boamp_data(api_response, date):
    """
    Parses the JSON response from the BOAMP API and extracts key information.
    :param api_response: JSON response data from the BOAMP API.
    :param date: Date string used for the filename.
    """
    total_count = api_response.get('total_count', 0)

    # Write the response to a file
    filename = f"data/boamp-{date}.json"
    with open(filename, 'w') as file:
        json.dump(api_response, file, indent=4)

    if total_count == 0:
        stdlog('Pas de nouvel avis pour ' + date)
        return

    if total_count > 99:
        errlog("Trop de résultat !!!")

    if 'results' in api_response and api_response['results']:
        for record in api_response['results']:
            

            """
            Get all data 
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
                titulaires = record.get('titulaire',[])
            except:
                titulaires = ''
            deadline = record.get('datelimitereponse', 'Non disponible')
            try:
                date_object = datetime.fromisoformat(deadline)
                deadline = date_object.strftime("%Y-%m-%d")
            except:
                pass
            
            donnees_brut = record.get('donnees',{})
            donnees = json.loads(donnees_brut)

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


            # Add text to the message
            message = '<strong>Acheteur : </strong>' + acheteur + '\n\n'
            if ref:
                message += '<strong>Référence marché : </strong>' + ref + '\n\n'
            message += '<strong>Services : </strong>' + services_list + '\n\n'
            message += '<strong>Type de marché : </strong>' + typemarche + '\n\n' 
            if valeur:
                message += '<strong>Valeur du marché : </strong>' + valeur + ' ' + devise + '\n\n'
            if lots:
                message += '<strong>Marché alloti : </strong>✅\n\n'
                for lot in lots_data:
                    intitule = lot.get('INTITULE')
                    num = lot.get('NUM')
                    info = lot.get('INFO_COMPL')
                    message += '\tLot '+ num + " : " +  intitule + '\n\n'
                    message += '\t\t'+info+'\n\n'
            if deadline:
                message += '<strong>Deadline : </strong>' + deadline + ' ('+ str(delai)+ ' jours)\n\n' 
            if offresrecues:
                message += '<strong>Offre(s) reçue(s) : </strong>' + offresrecues + '\n\n'
            if titulaires:
                titulaires_list = ', '.join(titulaires)
                message += '<strong>Titulaire(s) : </strong>' + titulaires_list + '\n\n'
            if duree:
                message +='<strong>Durée du marché (en mois) : </strong>' + duree + '\n\n'
            if annonce_lie:
                annonce_lie_list= ', '.join(annonce_lie)
                message += '<strong>Annonce(s) liée(s) : </strong>' + annonce_lie_list + '\n\n'
            message += '<strong>Avis : </strong>: ' + urlavis + '\n\n'
                
            
            # Add a title to the message
            title = status + '  ' + objet
            # Send MsTeams Card
            if not debug_mode:
                tomsteeams(nature,title,message)
            else:
                print(title + '\n' + remove_html_tags(message.replace('\n\n','\n')))
                print('-----------------------------------------------')
            
    else:
        errlog("No results found")



if __name__ == "__main__":
    print('''
    ,---.    .---.    .--.           ,---.   
    | .-.\  / .-. )  / /\ \ |\    /| | .-.\  
    | |-' \ | | |(_)/ /__\ \|(\  / | | |-' ) 
    | |--. \| | | | |  __  |(_)\/  | | |--'  
    | |`-' /\ `-' / | |  |)|| \  / | | |     
    /( `--'  )---'  |_|  (_)| |\/| | /(      
    (__)     (_)             '-'  '-'(__) 
            by Julien Mousqueton / Computacenter         
        ''')
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Script to fetch and process BOAMP data")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode (does not send messages to Teams)")
    parser.add_argument("-n", "--now", action="store_true", help="Force to scan today)")

    # Parse arguments
    args = parser.parse_args()

    # Main script execution
    debug_mode=args.debug
    today_mode=args.now

    if debug_mode:
        stdlog("DEBUG MODE")

    if today_mode:
        stdlog("TODAY MODE")

    # Load the .env file
    load_dotenv()

    # Use environment variables
    webhook_marche = os.getenv('WEBHOOK_MARCHE')
    webhook_attribution = os.getenv('WEBHOOK_ATTRIBUTION')

    if not webhook_marche or not webhook_attribution:
        errlog("Erreur: Au moins une des deux webhook URLs est manquante ou vide.")
        exit(1)

    today = datetime.now()

    # Calculate yesterday's date
    yesterday = today - timedelta(days=1)

    # Format yesterday's date to the desired format
    formatted_yesterday = yesterday.strftime("%Y-%m-%d")
    if today_mode:
        formatted_yesterday = today.strftime("%Y-%m-%d")

    stdlog('Récuperation des données du BOAMP pour le  ' + formatted_yesterday)
    data = fetch_boamp_data(formatted_yesterday)
    if data:
        stdlog('Analyse des données du BOAMP pour le ' + formatted_yesterday)
        parse_boamp_data(data, formatted_yesterday)
    else:
        errlog('Pas de donnée à analyser')
    stdlog('Fin !')
