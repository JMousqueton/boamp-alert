#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = "Julien Mousqueton"
__email__ = "julien.mousqueton_AT_computacenter.com"
__version__ = "1.3.1"

# Import for necessary Python modules
import requests
import json 
import pymsteams # To Publish Card on teams 
from datetime import datetime, timedelta 
import logging 
import argparse
import re # For removing HTML tag in debug mode 

# Housekeeping 
import gzip

# For checking python version
import sys

# For pushover notification
import http.client, urllib

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

def housekeeping(day_before_gzip, day_before_delete):
    """
    Nettoye le répertoire directory_path
    input : 
        day_before_gzip 
        day_before_delete 
    """
    directory_path = "./data"
    # Get the current date
    current_date = datetime.now()

    # Calculate the threshold dates
    threshold_gzip_date = current_date - timedelta(days=day_before_gzip)
    dbglog('Date avant compression : ' + str(threshold_gzip_date))
    threshold_delete_date = current_date - timedelta(days=day_before_delete)
    dbglog('Date avant effacement : ' + str(threshold_delete_date))
    pattern = re.compile(r'(\d{4}-\d{2}-\d{2})')
    file_date_format = '%Y-%m-%d'
    # Iterate through files in the directory
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)

        # Check if it's a file
        if os.path.isfile(file_path):
            # Extract date from the filename
            matches = pattern.findall(filename)

            if matches:
                file_date_str = matches[0]
            else:
                # stdlog("Ignored file with unexpected date format: " + filename)
                continue
            
            # Convert date string to datetime
            file_date = datetime.strptime(file_date_str, file_date_format)

            # Gzip the file if it's older than the threshold date for gzip
            if day_before_gzip > 0 and file_date < threshold_gzip_date and filename.endswith('.json'):
                gzip_filename = f"{filename}.gz"
                gzip_filepath = os.path.join(directory_path, gzip_filename)

                with open(file_path, 'rb') as f_in, gzip.open(gzip_filepath, 'wb') as f_out:
                    f_out.writelines(f_in)

                # Remove the original .json file
                os.remove(file_path)
                stdlog("Compression de " + filename)

            # Delete the file if it's a gzip or json file and older than the threshold date for deletion
            elif day_before_delete > 0 and (filename.endswith('.gz') or filename.endswith('.json')) and file_date < threshold_delete_date:
                os.remove(file_path)
                stdlog ("Effacement de : " + filename)


def format_large_number(number_str):
    """
    Converti number_str au format 1K ou 1M ... 
    """
    try:
        number = float(number_str)
        if number >= 1000000:
            formatted_number = f"{number / 1000000:.0f}M"
        elif number >= 1000:
            formatted_number = f"{number / 1000:.0f}k"
        else:
            formatted_number = f"{number:.2f}"
        return formatted_number
    except ValueError:
        return "Invalid input"


def toPushover(message):
    """
    Envoi une notification vers PushOver.net 
    input :
        message : string  
    """
    if USER_KEY and API_KEY and message:
        stdlog('Envoi d\'une notification PushOver')
        #load_dotenv()
        #USER_KEY=os.getenv('PUSH_USER')
        #API_KEY= os.getenv('PUSH_API')
        conn = http.client.HTTPSConnection("api.pushover.net:443")
        conn.request("POST", "/1/messages.json",
        urllib.parse.urlencode({
                "token": API_KEY,
                "user": USER_KEY,
                "message": message,
                "html": 1
                }), { "Content-type": "application/x-www-form-urlencoded" })
        conn.getresponse()
    #else:
    #    stdlog('Erreur d\'envoi de la notification PushOver')


def fetch_boamp_data(date, select_option=None):
    """
    Fetches data from the BOAMP API for a given date.
    :param date: A string representing the date in the format 'yyyy-MM-dd'.
    :param attribution_only: A boolean indicating whether to filter for attribution announcements only.
    :return: JSON response data.
    """
    year, month, day = date.split('-')
    search = "date_format(dateparution, 'yyyy') = '" + year + "' and date_format(dateparution, 'MM') = '"+month+"' and date_format(dateparution, 'dd') = '"+day+"' and ("
    query = ' OR '.join([f'dc = "{code}"' for code in descripteurs_list])
    search += query + ")"
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
        errmsg = "HTTP Error: " + str(errh)
        stdlog(errmsg)
        toPushover(errmsg)
    except requests.exceptions.ConnectionError as errc:
        errmsg = "Error Connecting: " + str(errc)
        stdlog(errmsg)
        toPushover(errmsg)
    except requests.exceptions.Timeout as errt:
        errmsg = "Timeout Error: " + str(errt)
        stdlog(errmsg)
        toPushover(errmsg)
    except requests.exceptions.RequestException as err:
        errmsg = "Other Error: " + str(err)
        stdlog(errmsg)
        toPushover(errmsg)

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
            status = ""
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


def fetch_all_keywords(api_url):
    """
    recupère tous les mots clefs dans la base du BOAMP 
    input : 
        api_url 
    output : 
        liste des mots clefs 
    """
    limit = 100
    offset = 0
    all_results = []

    while True:
        # Update the offset in the URL
        current_url = f"{api_url}&offset={offset}"

        # Send an HTTP GET request to the updated URL
        response = requests.get(current_url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()

            # Extract and append results to the list
            results = data.get('results', [])
            all_results.extend(results)

            # Check if there are more results
            if len(results) < limit:
                break  # No more results, exit the loop

            # Increment the offset for the next request
            offset += limit

        else:
            stdlog("Erreur de récupuration des mots clef. Status code: "+ str(response.status_code))
            break
    return all_results

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
        toPushover("Il y a plus de 100 résultats")
    stdlog('Extraction des données ...')
    if 'results' in api_response and api_response['results']:
        for record in api_response['results']:
            """
            Grab all data in variables 
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
        
            ###
            # Lecture  des données JSON du champs donnees
            ###
            donnees_brut = record.get('donnees',{})
            donnees = json.loads(donnees_brut)
            
            ## Titulaires 
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
            
            
             ## deadline 
            deadline = record.get('datelimitereponse', 'Non disponible')
            try:
                date_object = datetime.fromisoformat(deadline)
                deadline = date_object.strftime("%Y-%m-%d")
            except:
                pass
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
            
            ## Montant 
            try:
                devisetotal = donnees['OBJET']['CARACTERISTIQUES']['VALEUR_TOTALE']['@DEVISE']
                montanttotal = donnees['OBJET']['CARACTERISTIQUES']['VALEUR_TOTALE']['#text']
            except:
                try:
                    devisetotal = donnees['ATTRIBUTION']['DECISION']['RENSEIGNEMENT']['MONTANT']['@DEVISE']
                    montanttotal = donnees['ATTRIBUTION']['DECISION']['RENSEIGNEMENT']['MONTANT']['#text']
                except:
                    try:
                        devisetotal = donnees['OBJET']['LOTS']['LOT']['VALEUR']['@DEVISE']
                        montanttotal = donnees['OBJET']['LOTS']['LOT']['VALEUR']['#text']
                    except:
                        devisetotal = ''
                        montanttotal = ''
            try:
                devise = donnees['OBJET']['CARACTERISTIQUES']['VALEUR']['@DEVISE']
                valeur = donnees['OBJET']['CARACTERISTIQUES']['VALEUR']['#text']
            except:
                 devise = ''
                 valeur = ''
            
            ## Reférence 
            try:
                ref = donnees['CONDITION_ADMINISTRATIVE']['REFERENCE_MARCHE']
            except:
                ref = '' 
            if not ref:
                try:
                    ref = donnees['OBJET']['REF_MARCHE']
                except:
                    ref = ''
            ## Max participants 
            try:
                offresattendues = donnees['PROCEDURE']['ACCORD_CADRE']['NB_MAX_PARTICIPANTS']
            except:
                offresattendues = ''
            
            ## Durée 
            try:
                duree = donnees.get('OBJET', {}).get('DUREE_DELAI', {}).get('DUREE_MOIS', '')
            except:
                duree = ''
            
            ## Lots 
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
                offresrecues = donnees.get('ATTRIBUTION', {}).get('DECISION', {}).get('RENSEIGNEMENT', {}).get('NB_OFFRE_RECU', '')
            except:
                try: 
                    if nblots:
                       offresrecues = [f"Lot {index + 1} : {item['RENSEIGNEMENT']['NB_OFFRE_RECU']}" for index, item in enumerate(donnees.get("ATTRIBUTION", {}).get("DECISION", []))]
                       offresrecues = ", ".join(offresrecues)
                except:
                    offresrecues = ''    
            
            ## Annonces liées 
            try: 
                annonce_lie = record.get('annonce_lie', [])
            except: 
                annonce_lie = ''
            urlavis = record.get('url_avis', 'Not available')
            

            # Create the message for msteams card 
            message=''
            if pubdate:
                message+='<strong>' + pubdate + '</strong>\n\n'
            message += '<strong>Acheteur : </strong>' + acheteur + '\n\n'
            if ref:
                message += '<strong>Référence marché : </strong>' + ref + '\n\n'
            message += '<strong>Services : </strong>' + services_list + '\n\n'
            if typemarche == "Marchés entre 90 k€ et seuils européens" and seuilmarches: 
                typemarche = typemarche.replace('seuils européens',seuilmarches)
            message += '<strong>Type de marché : </strong>' + typemarche + '\n\n' 
            if valeur:
                message += '<strong>Valeur du marché : </strong>' + format_large_number(valeur) + ' ' + devise + '\n\n'
            elif montanttotal:
                message += '<strong>Valeur du marché : </strong>' + format_large_number(montanttotal) + ' ' + devisetotal + '\n\n'
            if lots:
                message += '<strong>Marché alloti : </strong>✅\n\n'
                try: 
                    counter = 1
                    for lot in lots_data:
                        intitule = lot.get('INTITULE','')
                        if not intitule:
                            intitule = lot.get('DESCRIPTION')
                        num = lot.get('NUM')
                        info = lot.get('INFO_COMPL','')
                        deviselot = lot.get('VALEUR',{}).get('@DEVISE','')
                        montantlot = lot.get('VALEUR',{}).get('#text','')
                        if not num:
                            if "lot" not in intitule.lower():
                                message += '\t Lot ' + str(counter) + ' : ' + intitule + '\n\n'
                                counter += 1 
                            else:    
                                message += '\t' + intitule + '\n\n' 
                        else:   
                            message += '\tLot '+ num + " : " +  intitule + '\n\n'
                        if montantlot:
                            message += '\t\tValeur du lot : ' + format_large_number(montantlot) + ' ' + deviselot + '\n\n'
                        message += '\t\t'+info+'\n\n'
                except: 
                    pass
            if offresattendues:
                message += '<strong>Offres maximales attendues : </strong>' + str(offresattendues) + '\n\n'
            if deadline:
                message += '<strong>Deadline : </strong>' + deadline + ' ('+ str(delai)+ ' jours)\n\n' 
            if offresrecues:
                message += '<strong>Offre(s) reçue(s) : </strong>' + offresrecues + '\n\n'
            if titulaires:
                message += '<strong>Titulaire(s) : </strong>' + titulaires + '\n\n'
            if duree:
                message +='<strong>Durée du marché (en mois) : </strong>' + duree + '\n\n'
            if annonce_lie:
                annonce_lie_list = ', '.join(['<a href="https://www.boamp.fr/pages/avis/?q=idweb:' + item + '">' + item + '</a>' for item in annonce_lie])
                message += '<strong>Annonce(s) liée(s) : </strong>' + annonce_lie_list + '\n\n'
            message += '<strong>Avis : </strong> ' + urlavis + '\n\n'
            
            # Ajout de l'icone en fonction du montant du marché 
            logomontant = '❓'
            if montanttotal and nature == "APPEL_OFFRE": 
                if float(montanttotal) > float(montant3):
                    logomontant = '💰💰💰'
                elif float(montanttotal) > float(montant2):
                    logomontant = '💰💰'
                elif float(montanttotal) > float(montant1):
                    logomontant = '💰'
                elif "entre" in typemarche:
                    logomontant= '❌'
                # Disable since no flag in Windows emoji :(  
                #elif typemarche == "Marchés européens":
                #    logomontant += '🇪🇺'
            elif "entre" in typemarche:
                    logomontant= '❌'
            elif "MAPA" in typemarche:
                logomontant = "⬇️"
            
            # Ajout du logo en fonction des services du marché 
            logoservices_list = []
            if "maintenance" in services_list.lower():
                logoservices_list.append("🧰")
            if "logiciel" in services_list.lower() or "progiciel" in services_list.lower():
                logoservices_list.append("💿")
            if "prestations" in services_list.lower() or "assistance" in services_list.lower():
                logoservices_list.append("👥")
            if "matériel" in services_list.lower():
                logoservices_list.append("💻")
            if "imprimerie" in services_list.lower():
                logoservices_list.append("🖨️")
            if "internet" in services_list.lower():
                logoservices_list.append("🌍")
            if "assistance" in services_list.lower():
                logoservices_list.append("🆘")
            if "téléphonie" in services_list.lower() or "télécommunications" in services_list.lower():
                logoservices_list.append('📞')
            ## Affiche le logo du montant uniquement pour les avis de marchés / modification 
            if nature == "APPEL_OFFRE":
                if logomontant and logoservices_list:
                    logoservice = " ".join(logoservices_list)
                    logostring = '  (' + logomontant + ' | ' + logoservice +') '
                elif logomontant and not logoservices_list:
                    logostring = '  (' + logomontant  +') '
                elif not logomontant and logoservices_list:
                    logoservice = " ".join(logoservices_list)
                    logostring = '  (' + logoservice + ') '
            else:
                logoservice = " ".join(logoservices_list)
                logostring = ' (' + logoservice + ') '
            ## Creation du titre 
            title = '['+ID+'] ' + status + logostring + objet
            
            # Envoie dans msteams
            if not debug_mode:
                tomsteeams(nature,title,message)
                i+=1 
            else:
                print(title + '\n' + remove_html_tags(message.replace('\n\n','\n')))
                print('-----------------------------------------------')
    else:
        errlog("Pas de résultat trouvé")

    stdlog(str(i) + ' message(s) envoyé(s) dans msteams')


def showlegend(debug=False):
    ''' 
    affiche la legende 
    '''
    message = '<table border="0"><tr><th>Logo</th><th>Description</th></tr>'
    message += '<tr><td>💰</td><td>Marché supérieur à ' +  format_large_number(str(montant1)) + ' €</td></tr>'
    message += '<tr><td>💰💰</td><td>Marché supérieur à ' +  format_large_number(str(montant2)) + ' €</td></tr>'
    message += '<tr><td>💰💰💰</td><td>Marché supérieur à ' +  format_large_number(str(montant3)) + ' €</td></tr>'
    message += '<tr><td>❌</td><td>Marché entre 90k€ et ' + seuilmarches + '</td></tr>'
    message += '<tr><td>❌</td><td>Marché inférieur à 90k€ (MAPA)</td></tr>'
    message += '<tr><td>❓</td><td>Marché d\'un montant inconnu ou compris entre ' + seuilmarches +  ' et ' + format_large_number(str(montant1)) + ' €</td></tr>'
    message += '<tr><td>💿</td><td>Marché identifié comme un marché <strong>logiciel</strong></td></tr>'
    message += '<tr><td>🧰</td><td>Marché identifié comme un marché de <strong>maintenance</strong></td></tr>'
    message += '<tr><td>👥</td><td>Marché identifié comme un marché de <strong>prestation de service</strong></td></tr>'
    message += '<tr><td>🆘</td><td>Marché identifié comme un marché de <strong>d\'assistance</strong></td></tr>'
    message += '<tr><td>💻</td><td>Marché identifié comme un marché de <strong>matériel</strong></td></tr>'
    message += '<tr><td>🖨️</td><td>Marché identifié comme un marché de <strong>matériel d\'impression</strong></td></tr>'
    message += '<tr><td>🟢</td><td>Avis de marché</td></tr>'
    message += '<tr><td>🟠</td><td>Modification d\'un avis de marché</td></tr>'
    message += '<tr><td>🏆</td><td>Avis d\'attribution</td></tr></table>'
    current_date = datetime.now().date()
    message += '<BR><BR>(C) 2022-' + str(current_date.year) + ' Computacenter - Développé par Julien Mousqueton'

    if not debug:
        title = 'Légende'
        # envoi de la légende dans le channel "Attribution"
        tomsteeams('ATTRIBUTION',title,message)
        # envoi de la légende dans le channel "Avis de marché"
        tomsteeams('AVIS',title,message)
        stdlog('Publication de la légende')
    else:
        print('Légende :\n')
        print(remove_html_tags(message.replace('</td></tr>','\n').replace('</td><td>','\t').replace('</th></tr>','\n').replace('</th><th>','\t')))

'''
Main Program  
'''
if __name__ == "__main__":
    print('''
    ,---.    .---.    .--.           ,---.   
    | .-.\  / .-. )  / /\ \ |\    /| | .-.\  
    | |-' \ | | |(_)/ /__\ \|(\  / | | |-' ) 
    | |--. \| | | | |  __  |(_)\/  | | |--'  
    | |`-' /\ `-' / | |  |)|| \  / | | |     
    /( `--'  )---'  |_|  (_)| |\/| | /(      
   (__)    (_)              '-'  '-'(__) 
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
    parser.add_argument("-l", "--legende", action="store_true", help="Publie la légende dans le channel des avis de marché")
    parser.add_argument("-m", "--motclef", action="store_true", help="Affiche tous les mots clefs")

    # Parse arguments
    args = parser.parse_args()

    # Get arguments
    debug_mode=args.debug
    today_mode=args.now
    specified_date = args.date
    select_option = args.select 
    legende = args.legende
    motclef = args.motclef    

    ### Si option -m ou --motclef 
    if motclef: 
        api_url = "https://www.boamp.fr/api/explore/v2.1/catalog/datasets/liste-mots-descripteurs-boamp%2F/records?order_by=mc_libelle&limit=100&timezone=UTC&include_links=false&include_app_metas=false"
        all_results = fetch_all_keywords(api_url)

        for result in all_results:
            mc_code = result.get('mc_code', '')
            mc_libelle = result.get('mc_libelle', '')
            print(f"{mc_code}, {mc_libelle}")
        exit()

    ### Si mode debug
    if debug_mode:
        stdlog("DEBUG MODE")

    # Load the .env file
    load_dotenv()

    # Use environment variables
    webhook_marche = os.getenv('WEBHOOK_MARCHE')
    webhook_attribution = os.getenv('WEBHOOK_ATTRIBUTION')

    montant1 = "{:.2f}".format(float(os.getenv('MONTANT1','1000000')))
    montant2 = "{:.2f}".format(float(os.getenv('MONTANT2','2000000')))
    montant3 = "{:.2f}".format(float(os.getenv('MONTANT3','4000000')))

    seuilmarches = os.getenv('SEUILMARCHES','')

    legendemonthly= os.getenv('LEGENDE',False) 

    USER_KEY=os.getenv('PUSH_USER')
    API_KEY= os.getenv('PUSH_API')
    
    day_before_gzip = int(os.getenv("JOURS_AVANT_GZIP", 0))
    day_before_delete = int(os.getenv("JOURS_AVANT_EFFACEMENT", 0))  

    ### Si option -l ou --legend 
    if legende: 
        showlegend(debug_mode)
        exit()
    
    ### si LEGENDE=True dans .env et que nous sommes le 1er jour du mois  
    current_date = datetime.now().date()
    if legendemonthly and current_date.day == 1:
        showlegend(True)

    # Housekeeping 
    stdlog('🧹 Nettoyage') 
    if debug_mode:
        stdlog('🧹 ' + str(day_before_gzip) + ' jours avant de compresser les fichiers')
        stdlog('🧹 ' + str(day_before_delete) + ' jours avant d\'effacer les fichiers')
    housekeeping(day_before_gzip, day_before_delete)

    
    ## Get Keywords 
    descripteurs_list = os.getenv('DESCRIPTEURS', '').split(',')
    descripteurs_list = [word.strip() for word in descripteurs_list]

    if not descripteurs_list:
        errmsg = "Aucun code de descripteurs. Voir le fichier .env"
        stdlog(errmsg)
        toPushover(errmsg)
        exit(1)

    if not webhook_marche or not webhook_attribution:
        errmsg = "Erreur: Au moins une des deux webhook URLs est manquante ou vide."
        stdlog(errmsg)
        toPushover(errmsg)
        exit(1)

    # Determine the date to process
    if today_mode:
        date_to_process = datetime.now().strftime("%Y-%m-%d")
        stdlog("(!) Date forcée à aujourd'hui : " + date_to_process)
    elif specified_date:
        date_to_process = specified_date
        stdlog("(!) Date forcée manuellement : " + date_to_process)
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
        errmsg='Aucune données à analyser'
        stdlog(errmsg)
        toPushover(errmsg)
    
    stdlog('Fini !')