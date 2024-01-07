
# BOAMP Alert

Ce script Python est conçu pour récupérer les données des marchés publics du BOAMP (Bulletin officiel des annonces des marchés publics) via l'API, analyser les données et envoyer des notifications via Microsoft Teams. 
Il est particulièrement utile pour surveiller les appels d'offres publics et les mises à jour associées.


## Fonctionnalités

Récupération des données de l'API BOAMP basée sur une date spécifique.
Analyse des données récupérées pour extraire les informations pertinentes.
Envoi de notifications à Microsoft Teams avec des informations détaillées sur les appels d'offres publics.
Journalisation pour les messages standard, de débogage et d'erreur.
Variables d'environnement pour une configuration flexible.


## Prérequis


- Python 3.10+ 
- Bibliothèques externes : requests, pymsteams, json, logging, datetime, os, dotenv


## Installation

1) Assurez-vous que Python 3.10 minimum est installé sur votre système.
2) Installez les paquets Python requis :

```
pip3 install requests pymsteams python-dotenv
```

3) Clonez ou téléchargez ce script sur votre machine locale.

## Configuration 

1) Créez un fichier .env dans le même répertoire que le script.
2) Ajoutez les variables d'environnement suivantes au fichier .env :

```
DESCRIPTEURS=<mots-clés séparés par des virgules>
WEBHOOK_MARCHE=<URL du Webhook Microsoft Teams pour les annonces de marché>
WEBHOOK_ATTRIBUTION=<URL du Webhook Microsoft Teams pour les annonces d'attribution>
````

## Utilisation

- Exécutez le script :

```
python3 boamp.py
```
Le script récupérera automatiquement les données pour la journée précédente.
Des notifications contenant des informations détaillées seront envoyées aux canaux Microsoft Teams configurés.

## Options 

```
python3 boamp.py -h

    ,---.    .---.    .--.           ,---.   
    | .-.\  / .-. )  / /\ \ |\    /| | .-.\  
    | |-' \ | | |(_)/ /__\ \|(\  / | | |-' ) 
    | |--. \| | | | |  __  |(_)\/  | | |--'  
    | |`-' /\ `-' / | |  |)|| \  / | | |     
    /( `--'  )---'  |_|  (_)| |\/| | /(      
    (__)     (_)             '-'  '-'(__) 
            par Julien Mousqueton / Computacenter         
        
usage: boamp.py [-h] [-D] [-n] [-d YYYY-MM-DD] [-s {attribution,ao}]

Script to fetch and process BOAMP data

options:
  -h, --help            show this help message and exit
  -D, --debug           Active le mode debug (aucun message ne sera envoyé à msteams)
  -n, --now             Force la date du jour au lieu de J-1
  -d YYYY-MM-DD, --date YYYY-MM-DD
                        Spécifie la date du scan au format yyyy-mm-dd
  -s {attribution,ao}, --select {attribution,ao}
                        Selection de la nature de l'avis : 'attribution' ou 'ao' (Appel d'Offre)
  ```

## Exemple

![screenshot](.github/screenshot.png)


## Auteur

- [Julien Mousqueton](https://www.github.com/JMousqueton) CTO @ [Computacenter](https://www.computacenter.com)


## Remerciements

 - Mon collègue et ami Guillaume C. pour les idées et surtout la motivation 
 - La communauté Cyber qui m'a permis de me remettre au python avec le projet [Ransomware.live](https://www.ransomware.live)
