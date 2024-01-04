import requests
import json
import pymsteams
from datetime import datetime, timedelta
import logging

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

def determine_status(nature, record):
    """
    Determines the status based on the nature field.
    :param nature: The nature field from the record.
    :param record: The entire record from the response.
    :return: The determined status.
    """
    status = ""
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
            
            nature = record.get('nature')
            status = determine_status(nature, record)
            #### print("ID Web :", record.get('idweb', 'Not available'))
            acheteur = record.get('nomacheteur', 'Non disponible')
            objet = record.get('objet', 'Non disponible')
            services = record.get('descripteur_libelle')
            services_clean = ', '.join(services)
            services_list= services_clean.replace('Informatique (','').replace(')','')
            pubdate =  record.get('dateparution', 'Non disponible')

            typemarche = record.get('famille_libelle', 'Non disponible')
            try:
                devise = donnees['OBJET']['CARACTERISTIQUES']['VALEUR']['@DEVISE']
                valeur = donnees['OBJET']['CARACTERISTIQUES']['VALEUR']['#text']
            except:
                devise = ''
                valeur = ''
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
            try:
                duree = donnees.get('OBJET', {}).get('DUREE_DELAI', {}).get('DUREE_MOIS', '')
            except:
                duree = ''
            try:
                offresrecues = donnees.get('ATTRIBUTION', {}).get('DECISION', {}).get('RENSEIGNEMENT', {}).get('NB_OFFRE_RECU', 'Non renseigné')
            except:
                offresrecues = ''
            try: 
                annonce_lie = record.get('annonce_lie', [])
            except: 
                annonce_lie = ''
            urlavis = record.get('url_avis', 'Not available')

            if nature in ['RECTIFICATIF', 'APPEL_OFFRE']:
                # Add text to the message
                message = '<strong>Acheteur : </strong>' + acheteur + '\n\n'
                message += '<strong>Services : </strong>' + services_list + '\n\n'
                message += '<strong>Type de marché :</strong>' + typemarche + '\n\n' 
                if valeur:
                    message += '<strong>Valeur du marché : </strong>' + f"{int(valeur):,}" + ' ' + devise + '\n\n'
                if deadline:
                    message += '<strong>Deadline : </strong>' + deadline + '\n\n' 
                if duree:
                    message +='<strong>Durée du marché (en mois) : </strong>' + duree + '\n\n'
                if annonce_lie:
                    annonce_lie_list= ', '.join(annonce_lie)
                    message += '<strong>Annonce(s) liée(s) : </strong>' + annonce_lie_list + '\n\n'
                message += '<strong>Avis : </strong>: ' + urlavis + '\n\n'

                myTeamsMessage4marche.text(message)

                # Add a title to the message
                title = status + ' ' + objet
                myTeamsMessage4marche.title(title)

                # Send the message
                try:
                    myTeamsMessage4marche.send()
                except pymsteams.TeamsWebhookException as e:
                    print(f"Error sending message: {e}")

            if nature in ['ATTRIBUTION']:
                message = '<strong>Acheteur : </strong>' + acheteur + '\n\n'
                message += '<strong>Services : </strong>' + services_list + '\n\n'
                message += '<strong>Type de marché :</strong>' + typemarche + '\n\n' 
                if valeur:
                    message += '<strong>Valeur du marché : </strong>' + f"{int(valeur):,}" + ' ' + devise + '\n\n'
                if offresrecues:
                    message += '<strong>Offre(s) reçue(s) : </strong>' + offresrecues + '\n\n'
                if titulaires:
                    titulaires_list = ', '.join(titulaires)
                    message += '<stong>Titulaire(s) : </strong>' + titulaires_list + '\n\n'
                if duree:
                    message +='<strong>Durée du marché (en mois) : </strong>' + duree + '\n\n'
                if annonce_lie:
                    annonce_lie_list= ', '.join(annonce_lie)
                    message += '<strong>Annonce(s) liée(s) : </strong>' + annonce_lie_list + '\n\n'
                message += '<strong>Avis : </strong>: ' + urlavis + '\n\n'

                myTeamsMessage4attribution.text(message)

                # Add a title to the message
                title = status + ' ' + objet
                myTeamsMessage4attribution.title(title)

                # Send the message
                try:
                    myTeamsMessage4attribution.send()
                except pymsteams.TeamsWebhookException as e:
                    errlog("Error sending message: " + {e})
                
            #stdlog(status + '   ' + objet)

            
    else:
        errlog("No results found")

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


# Load the .env file
load_dotenv()

# Use environment variables
webhook_marche = os.getenv('WEBHOOK_MARCHE')
webhook_attribution = os.getenv('WEBHOOK_ATTRIBUTION')

if not webhook_marche or not webhook_attribution:
    errlog("Error: One or both webhook URLs are missing or empty.")
    exit(1)


# Create a connector card object
myTeamsMessage4marche = pymsteams.connectorcard(webhook_marche)
myTeamsMessage4attribution = pymsteams.connectorcard(webhook_attribution)

today = datetime.now()

# Calculate yesterday's date
yesterday = today - timedelta(days=1)

# Format yesterday's date to the desired format
formatted_yesterday = yesterday.strftime("%Y-%m-%d")

stdlog('Fetching BOAMP pour le  ' + formatted_yesterday)
data = fetch_boamp_data(formatted_yesterday)
if data:
    stdlog('Parsing BOAMP pour le ' + formatted_yesterday)
    parse_boamp_data(data, formatted_yesterday)
else:
    errlog('Pas de donnée à parser')
stdlog('Fin !')
