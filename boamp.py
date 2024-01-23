#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = "Julien Mousqueton"
__email__ = "julien.mousqueton_AT_computacenter.com"
__version__ = "2.0.0"

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

# Init compteurs 
cptao = 0  # compteur des avis de marché 
cptmodif = 0 # compteur des modification 
cptres = 0 # compteur d'avis d'attribution
cptother =0 # Compteur autres 

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
    global cptao
    global cptmodif
    global cptres
    global cptother
    match nature:
        case "APPEL_OFFRE":
            status = "🟢"
            cptao += 1 
        case "RECTIFICATIF":
            status = "🟠"
            cptmodif += 1
        case "R\u00e9sultat de march\u00e9":   # Vérifier la pertinence 
            status = "🏆"
            cptres += 1
        case "ATTRIBUTION":
            status = "🏆"
            cptres += 1
        case _:
            status = ""
            ctpother += 1
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

def translate(word):
    match word.lower():
        case "quality":
            return "Qualité : "
        case "price":
            return "Prix : "
        case "month":
            return "mois"
        case _:
            return word


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
            urlavis = record.get('url_avis', 'Not available')
            ###
            # Lecture  des données JSON du champs donnees
            ###
            montanttotal =''
            avisinitial = ''
            critere_pondere = ''
            ref = ''
            titulaire = ''
            date_reception_offres = ''
            dureemarche = ''
            nblots = 0
            donnees_brut = record.get('donnees',{})
            donnees = json.loads(donnees_brut)
            # Print the first key 
            # FNSimple
            # MAPA
            # EFORMS
            first_key = next(iter(donnees))
            #### MAPA ####
            if first_key == "MAPA" and nature == "ATTRIBUTION":
                try:
                    avisinitial = donnees['MAPA']['attribution']['avisInitial']['idWeb']
                except:
                    avisinitial = ''
                try:
                    montant = donnees['MAPA']['attribution']['attribution']['resultat']['attribue']['montant']['valeur']
                except:
                    montant = ''
                montanttotal = montant
            elif first_key == "MAPA" and nature == "APPEL_OFFRE":
                try:
                    duree_mois = donnees['MAPA']['initial']['natureMarche']['nbMois']
                except:
                    duree_mois = ''
                try:
                    date_reception_offres = donnees['MAPA']['initial']['delais']['receptionOffres']
                    date_object = datetime.fromisoformat(date_reception_offres)
                    date_reception_offres = date_object.strftime("%Y-%m-%d")
                except: 
                    date_reception_offres =''
                try:
                    ref = donnees['MAPA']['initial']['renseignements']['idMarche']
                except: 
                    ref =''
                try:
                    critere_pondere_list = donnees['MAPA']['initial']['criteres']['criterePondere']
                    critere_pondere = "<strong>Critères d'attribution :</strong><ul>"
                    for item in critere_pondere_list:
                        critere_pondere += "<li>  " +  item['critere'] + " : " + item['criterePCT'] + "%</li>"
                    critere_pondere += "</ul>\n\n"        
                except:
                    critere_pondere = ''
            elif first_key == "MAPA" and nature == "RECTIFICATIF":
                print("🛠️ A FAIRE : " + first_key + " " + nature)    
            #### FNSimple ####
            elif first_key == "FNSimple" and nature == "APPEL_OFFRE":
                try:
                    date_reception_offres = donnees['FNSimple']['initial']['procedure']['dateReceptionOffres']
                    date_object = datetime.fromisoformat(date_reception_offres)
                    date_reception_offres = date_object.strftime("%Y-%m-%d")
                except: 
                    date_reception_offres =''
                try:
                    duree_mois = donnees['FNSimple']['natureMarche']['dureeMois']
                except:
                    try: 
                        dureemarche = donnees['FNSimple']['initial']['natureMarche']['dureeMois'] + ' mois'
                    except:
                        dureemarche = ''
                try:
                    valeur_haute = donnees['FNSimple']['natureMarche']['valeurEstimee']['fourchette']['valeurHaute']
                except:
                    try:
                        valeur_haute = donnees['FNSimple']['initial']['natureMarche']['valeurEstimee']['fourchette']['valeurHaute']
                    except:
                        valeur_haute = ''
                montanttotal = valeur_haute
            elif first_key == "FNSimple" and nature == "ATTRIBUTION":
                print("🛠️ A FAIRE : " + first_key + " " + nature)
            #### EFORMS ####
            elif first_key == "EFORMS" and nature == "APPEL_OFFRE":
                print("🛠️ [" + ID + "] A FAIRE : " + first_key + " " + nature)
                try: 
                    procurement_projects = donnees['EFORMS']['ContractNotice']['cac:ProcurementProjectLot']
                    nblots = sum('cbc:ID' in project for project in procurement_projects)
                except:
                    nblots = ''

                if nblots > 1:
                    try:
                        critere_pondere = "<strong>Critères d'attribution :</strong><ul>"
                        for i in range(nblots):
                            critere_pondere_list = donnees['EFORMS']['ContractNotice']['cac:ProcurementProjectLot'][i]['cac:TenderingTerms']['cac:AwardingTerms']['cac:AwardingCriterion']['cbc:Description']['#text']
                            try:
                                descriptif = donnees['EFORMS']['ContractNotice']['cac:ProcurementProjectLot'][i]['cac:ProcurementProject']['cbc:Name']['#text'] + "<BR>"
                            except:
                                descriptif = ''
                            critere_pondere += "<li> Lot n°" + str(i+1) + " : " + descriptif + str(critere_pondere_list) + "</li>"
                        critere_pondere += "</ul>\n\n"
                    except:
 
                        try:
                            critere_pondere_list = donnees['EFORMS']['ContractNotice']['cac:ProcurementProjectLot']['cac:TenderingTerms']['cac:AwardingTerms']['cac:AwardingCriterion']['cac:SubordinateAwardingCriterion']
                            critere_pondere =  '<strong>Critères : </strong><ul>'
                            for item in critere_pondere_list:
                                critere_pondere  += "<li>"
                                for key, value in item.items():
                                    critere_pondere += translate(value.get('#text', ''))
                                critere_pondere += "</li>"
                            critere_pondere += "</ul>\n\n"    
                        except:
                                critere_pondere = ''
                try:
                    duree = donnees['EFORMS']['ContractNotice']['cac:ProcurementProjectLot']['cac:ProcurementProject']['cac:PlannedPeriod']['cbc:DurationMeasure']['#text']
                    unite = translate(donnees['EFORMS']['ContractNotice']['cac:ProcurementProjectLot']['cac:ProcurementProject']['cac:PlannedPeriod']['cbc:DurationMeasure']['@unitCode'])
                    dureemarche = duree + ' ' + unite 
                except:
                    dureemarche = '' 
                    

            elif first_key == "EFORMS" and nature == "ATTRIBUTION":
                print("🛠️ A FAIRE : " + first_key + " " + nature)
                try:
                    titulaire = donnees['EFORMS']['ContractAwardNotice']['ext:UBLExtensions']['ext:UBLExtension']['ext:ExtensionContent']['efext:EformsExtension']['efac:NoticeResult']['efac:LotTender']['efac:TenderReference']['cbc:ID']
                except:
                    titulaire = ''
            else:
                errmsg = "ERROR DONNEES : [" +ID + "]" + first_key + '(' + nature + ')'
                print('(!) ' + errmsg)
                toPushover(errmsg)
            
            ## Titulaire
            if not titulaire:
                try:
                    titulaires_list = record.get('titulaire',[])
                    # Check if the list has only one entry or multiple entries
                    if len(titulaires_list) == 1:
                        # If there's only one entry, just take that entry
                        titulaire = titulaires_list[0]
                    else:
                        # If there are multiple entries, join them with ', '
                        titulaire = ', '.join(titulaires_list)
                except:
                    titulaire = ''
            
            if not date_reception_offres:
                ## deadline 
                date_reception_offres = record.get('datelimitereponse', 'Non disponible')
                try:
                    date_object = datetime.fromisoformat(date_reception_offres)
                    date_reception_offres = date_object.strftime("%Y-%m-%d")
                except:
                    pass
            
            
            if date_reception_offres:
                target_date = datetime.strptime(date_reception_offres, "%Y-%m-%d")
                current_date = datetime.now()
                delai = (target_date - current_date).days
    

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
            if montanttotal:
                message += '<strong>Valeur maximale estimée du marché : </strong>' + format_large_number(str(montanttotal)) + '€\n\n' 
            if nblots > 1 :
                message += '<strong>Lots : </strong>' + str(nblots) +'\n\n'
            if critere_pondere:
                message += critere_pondere
            if date_reception_offres:
                message += '<strong>Deadline : </strong>' + date_reception_offres + ' ('+ str(delai)+ ' jours)\n\n' 
            if dureemarche:
                message += '<strong>Durée du marché : </strong>' +  dureemarche + '\n\n'
            if titulaire:
                message += '<strong>Titulaire(s) : </strong>' + titulaire + '\n\n'
            if avisinitial:
                #annonce_lie_list = ', '.join(['<a href="https://www.boamp.fr/pages/avis/?q=idweb:' + item + '">' + item + '</a>' for item in annonce_lie])
                annonce_lie_list = '<a href="https://www.boamp.fr/pages/avis/?q=idweb:' + avisinitial+ '">' + avisinitial + '</a>'
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
                    logomontant= '⬇️'
            #    # Disable since no flag in Windows emoji :(  
            #    #elif typemarche == "Marchés européens":
            #    #    logomontant += '🇪🇺'
            elif "entre" in typemarche:
                    logomontant= '⬇️'
            elif "MAPA" in typemarche:
                logomontant = "❌"
            
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
            if "consommable" in services_list.lower():
                logoservices_list.append("♻️")
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
    message += '<tr><td>⬇️</td><td>Marché entre 90k€ et ' + seuilmarches + '</td></tr>'
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
    parser.add_argument("-S", "--statistiques", action="store_true", help="Force la création des statistiques quand l'option début est activée")

    # Parse arguments
    args = parser.parse_args()

    # Get arguments
    debug_mode=args.debug
    today_mode=args.now
    specified_date = args.date
    select_option = args.select 
    legende = args.legende
    motclef = args.motclef    
    statistiquesdebug = args.statistiques

    if statistiquesdebug and not debug_mode:
        stdlog("Erreur -S/--statistiques ne peut être utilisé uniquement avec -D/--debug")
        exit(1)

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

    statistiques = os.getenv('STATISTIQUES',False) 

    USER_KEY=os.getenv('PUSH_USER')
    API_KEY=os.getenv('PUSH_API')
    
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
    
    ## Ecriture des statistiques dans statistiques.json
    if (statistiques and not debug_mode) or (statistiquesdebug and debug_mode):
        file_path = "statistiques.json"
        # Load existing data from the file
        try:
            with open(file_path, "r") as json_file:
                existing_data = json.load(json_file)
        except FileNotFoundError:
            existing_data = {"statistiques": []}

        existing_dates = [entry["date"] for entry in existing_data["statistiques"]]
        if date_to_process in existing_dates:
            stdlog("La date " + date_to_process + " existe déjà. Les statistiques n\'ont pas été mises à jour")
        else:
            data = {
            "date": date_to_process,
            "Marche": cptao,
            "Modification": cptmodif,
            "Notification": cptres,
            "Autre": cptother
            }
            existing_data["statistiques"].append(data)

            with open(file_path, 'w') as json_file:
                json.dump(existing_data, json_file, indent=4)
            stdlog('Ecriture des statistiques pour ' + date_to_process)

    stdlog('Fini !')