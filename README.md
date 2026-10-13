# GP7 Web

Socle web de gestion academique pour les entites de l'UEH. L'interface et le code metier utilisent des noms francophones; les identifiants restent sans accents pour assurer la compatibilite Python et SQL.

## Technologies

- Django 4.2.16
- PyMySQL avec le moteur MySQL de Django
- MySQL ou MariaDB fourni par XAMPP
- Applications Django regroupees dans `applications/`
- Python 3.12 est la version officiellement prise en charge par Django 4.2.16. Le venv local est en Python 3.13.7; les tests passent, mais cette combinaison n'est pas une cible officiellement certifiee par Django 4.2.

## Installation locale

1. Installer Python 3.12 et demarrer MySQL dans le panneau XAMPP.
2. Creer la base `config_web` avec l'interclassement `utf8mb4_unicode_ci` dans phpMyAdmin; le script `creer_base.sql` la cree aussi. Utiliser une base neuve, sans ancien historique de migrations Django.
3. Dans l'invite de commandes, depuis ce dossier, creer et activer l'environnement, puis installer les dependances :

   ```bat
   python -m venv venv
   venv\Scripts\activate
   python -m pip install -r requirements.txt
   ```

4. Creer le fichier local de configuration et verifier `DB_NAME=config_web` ainsi que les autres variables MySQL :

   ```bat
   copy .env.example .env
   ```

5. Preparer les tables et creer le compte administrateur :

   ```bat
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver
   ```

6. Ouvrir `http://127.0.0.1:8000/` pour le tableau de bord et `http://127.0.0.1:8000/admin/` pour l'administration initiale.

Le bouton « Demander une admission » ouvre le portail `admission_ueh` à `/admission/` par défaut. En développement, ouvrir deux terminaux : démarrer GP7 avec `python manage.py runserver 127.0.0.1:80`, puis Admission sur `127.0.0.1:8001` avec `DJANGO_SCRIPT_NAME=/admission` et `configuration.development_settings`. Le proxy de développement de GP7 transmet `/admission/` vers Admission; l'adresse devient `http://127.0.0.1/admission/`. Si le port 80 n'est pas disponible, démarrer GP7 sur `8000` et ouvrir `http://127.0.0.1:8000/admission/`. En production, utiliser le proxy Nginx de `deploy/nginx.conf` derrière le serveur HTTPS. Les applications conservent chacune leur configuration, migrations et base de données. Le lien est modifiable avec `ADMISSION_PORTAL_URL`.

En mode debug, les demandes de reinitialisation affichent le lien dans le terminal. Pour l'envoi reel, regler `DJANGO_DEBUG=0`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` ou `EMAIL_USE_SSL`, ainsi que `DEFAULT_FROM_EMAIL` dans `.env`. L'application n'envoie jamais le mot de passe lui-meme, uniquement un lien de reinitialisation temporaire.

Les tests des notes, inscriptions, paiements, affectations et rapports sont des tests Django et necessitent une base de test MySQL temporaire. Les lancer avec leurs etiquettes d'application :

```bat
python manage.py test applications.notes.tests applications.inscriptions.tests applications.rapports.tests
```

## Jeu de donnees de demonstration

La base locale peut etre simulee sans conserver de changement avec `python manage.py reinitialiser_donnees_demo --dry-run`.

Pour vider les donnees applicatives puis recreer un jeu complet pour FAMV, FLA, IERAH/ISSERS et FASCH, lancer `python manage.py reinitialiser_donnees_demo --confirmer-reinitialisation`. Cette commande conserve les comptes superutilisateurs et leurs mots de passe, mais efface les autres donnees. Faire une sauvegarde avant de la lancer; le script de reinitialisation ne s'applique pas a une base de production.

Le jeu inclut des comptes Registrariat, professeur et etudiant, deux programmes par entite, des periodes precedentes et actuelles, des cours obligatoires et optionnels, des paiements complets/partiels/en attente, des inscriptions validees/en attente, des notes publiees/non publiees, des dossiers, des actes et des soutenances. Les utilisateurs demo ont le format `demo_gp7_registrariat_<entite>`, `demo_gp7_prof_<entite>_<programme>` et `demo_gp7_etudiant_<entite>_<programme>_<scenario>`. Un mot de passe local aleatoire, commun a ces comptes, est affiche une fois par la commande.

Toutes les personnes, notes, references et operations sont fictives. Les versions de reglement sont marquees `DEMO-CDC`; leurs valeurs servent a tester les ecrans et ne remplacent pas les reglements officiels des entites.

La cle `DJANGO_SECRET_KEY` de `.env.example` est un exemple local. Elle doit etre remplacee par une valeur aleatoire avant tout deploiement. Ne jamais committer `.env`.

## Templates Django dans VS Code

Les fichiers `.django` et les fichiers HTML du dossier `templates/` sont associes au langage `django-html`. L'extension djLint est selectionnee comme formateur et s'execute dans le `venv` du projet a l'enregistrement. Installer les dependances du projet avec `python -m pip install -r requirements.txt`; l'extension `jraylan.django-template-extension`, recommandee par VS Code, ajoute la coloration syntaxique Django/Jinja.

## Organisation

- `applications/comptes/` : comptes GP7 et Admission, authentification Allauth, roles, profils et photos
- `applications/referentiels/` : entites, regimes, programmes, cours, periodes, versions de reglements et affectations de professeurs
- `applications/inscriptions/` : inscriptions pedagogiques, choix de cours, tarifs et paiements de scolarite
- `applications/notes/` : evaluations, notes et publication
- `applications/rapports/` : indicateurs et documents academiques
- `applications/audit/` : journal des actions sensibles
- `templates/` et `static/` : interface responsive partagee

Les seuils et conditions d'admissibilite ne sont pas fixes globalement : chaque entite doit avoir des regles datees et versionnees, validees a partir de son reglement officiel. L'administration Django initiale est reservee au superutilisateur; l'espace etudiant ne presente que ses inscriptions et notes publiees. Les rapports agregent les inscriptions, profils renseignes, dossiers, actes et soutenances dans un perimetre d'entite, avec export CSV. Les identifiants et photos d'etudiants ne sont pas inclus dans cet export.

Le professeur voit la liste des etudiants inscrits uniquement aux cours qui lui sont affectes. L'etudiant peut declarer un paiement pour un tarif actif d'une periode ouverte; le registrariat ne traite que les paiements de son entite, et chaque decision est journalisee. Une demande d'inscription n'est recevable qu'apres paiement integral confirme, reste en attente jusqu'a la verification explicite des conditions par le registrariat, puis permet de choisir les cours affectes pendant la periode ouverte. Les regles d'admissibilite sont encore confirmees manuellement, sans calcul automatique pour toutes les entites.

L'importation des notes depuis un fichier Excel `.xlsx` est disponible dans l'espace de saisie des cours. Le fichier utilise les colonnes `code_etudiant`, `evaluation`, `note` et `coefficient`, dans cet ordre; le code doit correspondre au code officiel du profil etudiant.

Le Registrariat emet les actes depuis `Rapports > Emission des actes`; le personnel ne peut agir que dans son entite. Les actes delivres sont ensuite telechargeables en PDF depuis le dossier de l'etudiant. Le document comprend une formulation adaptee au type d'acte, la reference, les donnees du dossier et un espace de signature et de sceau du Registrariat; le releve detaille les evaluations publiees et leurs moyennes ponderees. La generation est journalisee. Ces modeles sont utilisables des maintenant et pourront etre ajustes aux gabarits officiels transmis par la DReg.

Les soutenances se planifient et se mettent a jour dans `Rapports > Soutenances`; le passage au statut « soutenue » exige une note. Le PV est consultable et telechargeable en PDF par l'etudiant concerne et le Registrariat de son entite. Les actions de creation, modification et generation PDF sont journalisees.

Le Registrariat ouvre et met a jour les dossiers d'etudes dans `Rapports > Dossiers d'etudes`. Les dossiers `en cours` n'ont pas de date de cloture; les statuts `ferme`, `abandon` et `diplome` exigent une date de cloture et conservent leur motif. La creation et les modifications sont journalisees, et les dossiers sont cloisonnes par entite.

Les listes d'etudiants s'ouvrent depuis `Rapports > Listes d'etudiants` et peuvent etre filtrees par programme, periode, niveau, cours et statut, puis imprimees depuis le navigateur. Le code etudiant officiel est affiche sur cette liste; elle n'est accessible qu'au superutilisateur et au Registrariat de l'entite.

Un recu PDF est disponible dans l'historique des paiements pour chaque versement valide. Il indique le montant du versement, le total confirme, le tarif, le solde restant, la reference et le membre du Registrariat qui l'a valide. Les paiements en attente ou refuses n'ont pas de lien de recu.

## Seuils de passage

Pour le cas ambigu retenu dans le cahier des charges, le service `applications/notes/services/famv_2016.py` classe la moyenne annuelle ainsi : a partir de 65/100, admis ; de 60 a moins de 65/100, reprise des cours sous 65 ; sous 60/100, echec. Les seuils sont inclusifs a 60 pour la reprise et a 65 pour l'admission. Ce choix simplifie les exceptions presentes dans les reglements d'entite ; les autres seuils et conditions propres a chaque entite restent a confirmer par le Registrariat.

Le service ne calcule pas la moyenne annuelle. Les rapports de cours utilisent les notes publiees et les seuils versionnes `seuil_reussite_cours` et `seuil_reprise_cours` de la regle academique en vigueur a la date de debut de la periode. Sans seuil de reprise explicite, celui-ci reprend le seuil de reussite pour conserver le comportement binaire des anciennes regles. Une entite sans seuil de reussite applicable est explicitement signalee « non configuree ».

## Examens et constantes

Le Registrariat peut programmer, modifier ou annuler un examen dans `Notes > Programmer les examens`, en choisissant le cours, la periode, l'horaire, la salle et les consignes. Les conflits de salle et de creneau pour un meme cours sont refuses et les modifications sont journalisees. Les professeurs voient les examens de leurs cours affectes; les etudiants ne voient que ceux de leurs cours selectionnes dans une inscription validee. Le calendrier est en lecture seule pour ces deux roles.

Le Registrariat gere les versions de constantes dans `Referentiels > Constantes academiques`. Les valeurs versionnees dans `RegleAcademique.parametres` comprennent `seuil_reussite_cours`, `seuil_reprise_cours`, `note_eliminatoire`, `credits_requis` et `mentions` (objet JSON associant une mention a son seuil sur 100). Les autres cles JSON deja presentes sont conservees lors d'une modification. Cette interface ne change pas la decision de passage convenue : 65 admis, de 60 a moins de 65 en reprise, moins de 60 en echec.
