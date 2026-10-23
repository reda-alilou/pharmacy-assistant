# Développement d’une application Full Stack

## Plateforme collaborative d’analyse et de visualisation de données

## 1. Contexte

Une entreprise spécialisée dans les services numériques souhaite développer une plateforme permettant à ses collaborateurs et à ses clients de centraliser, explorer, analyser et visualiser différents jeux de données.

Actuellement, les analyses sont réalisées de manière dispersée à partir de fichiers CSV, Excel ou de différentes sources de données. L’entreprise souhaite disposer d’une application web moderne permettant de transformer ces données en informations exploitables grâce à des tableaux de bord interactifs.

L’objectif du projet est de concevoir et développer un **MVP (Minimum Viable Product)** de cette plateforme en utilisant principalement **React.js** pour le **Front-end** et **Node.js** pour le **Back-end**.

Le projet sera réalisé **en groupe** sur une durée d’environ **6 semaines**.

## 2. Objectifs du projet

L’application devra permettre de couvrir l’ensemble du cycle d’exploitation d’un jeu de données :

**Importation → Exploration → Analyse → Visualisation → Partage**

Elle devra notamment permettre aux utilisateurs :

- de gérer leurs jeux de données ;
- d’explorer leur contenu ;
- d’effectuer différentes analyses ;
- de construire des indicateurs ;
- de visualiser les résultats ;
- de sauvegarder leurs analyses ;
- de partager certains résultats.

Le domaine des données pourra être choisi par chaque équipe : **transport, énergie, environnement, ventes, finance, éducation, Open Data, mobilité**, etc.

## 3. Utilisateurs de la plateforme

L’application devra prévoir **au minimum trois types d’accès**.

### 3.1. Visiteur

Le visiteur pourra :

- consulter la présentation de la plateforme ;
- consulter éventuellement certains dashboards publics ;
- créer un compte ;
- s’authentifier.

### 3.2. Utilisateur / Data Analyst

Après authentification, l’utilisateur pourra :

- gérer son profil ;
- importer et gérer ses datasets ;
- explorer les données ;
- effectuer des analyses ;
- consulter des statistiques ;
- construire des visualisations ;
- créer des tableaux de bord ;
- sauvegarder et partager ses analyses.

### 3.3. Administrateur

L’administrateur pourra :

- gérer les utilisateurs ;
- superviser les datasets présents sur la plateforme ;
- consulter l’activité générale de l’application ;
- disposer d’un tableau de bord d’administration.

## 4. Gestion des datasets

La plateforme devra permettre à un utilisateur d’ajouter un nouveau jeu de données.

Pour chaque dataset, l’utilisateur pourra renseigner certaines informations telles que :

- le titre ;
- la description ;
- la catégorie ;
- la source des données.

L’application devra permettre l’importation de données **au minimum au format CSV**.

Vous pouvez éventuellement ajouter d’autres sources :

- JSON ;
- Excel ;
- API externe ;
- Open Data.

Une fois importées, les données devront pouvoir être consultées et exploitées depuis l’application.

## 5. Exploration des données

L’utilisateur devra disposer d’un espace permettant d’explorer un dataset.

Il pourra notamment :

- visualiser les données sous forme tabulaire ;
- rechercher des informations ;
- filtrer les données ;
- trier les résultats ;
- consulter les principales caractéristiques du dataset.

L’application pourra également présenter automatiquement certaines informations telles que :

- nombre de lignes ;
- nombre de colonnes ;
- types de données ;
- valeurs manquantes ;
- statistiques descriptives.

## 6. Analyse des données

L’utilisateur devra pouvoir effectuer différentes opérations d’analyse à partir des données disponibles.

Selon le dataset utilisé, l’application pourra notamment calculer :

- des sommes ;
- des moyennes ;
- des minimums et maximums ;
- des répartitions ;
- des classements ;
- des évolutions dans le temps ;
- différents indicateurs métiers.

Les indicateurs proposés devront être cohérents avec le domaine choisi par l’équipe.

## 7. Visualisation et Dashboard

L’application devra permettre de présenter les résultats des analyses sous forme graphique.

Plusieurs types de visualisations devront être proposés, par exemple :

- histogrammes ;
- courbes ;
- graphiques circulaires ;
- cartes KPI ;
- autres représentations pertinentes.

L’utilisateur devra pouvoir regrouper plusieurs indicateurs et visualisations afin de construire un **dashboard interactif**.

Le dashboard pourra proposer différents filtres afin d’actualiser dynamiquement les résultats affichés.

## 8. Gestion des analyses

L’utilisateur pourra sauvegarder certaines analyses afin de les consulter ultérieurement.

Une analyse pourra contenir notamment :

- le dataset utilisé ;
- les filtres appliqués ;
- les indicateurs sélectionnés ;
- les visualisations choisies.

Une analyse pourra être :

- privée ;
- ou partageable avec d’autres utilisateurs.

Les équipes pourront proposer un mécanisme permettant de rendre certains dashboards accessibles publiquement.

## 9. Fonctionnalité avancée

Chaque groupe devra développer **au moins trois fonctionnalités avancées liées aux données**.

Par exemple :

- détection de valeurs aberrantes ;
- analyse des valeurs manquantes ;
- calcul d’un score de qualité des données ;
- analyse de corrélation ;
- recommandation automatique de graphiques ;
- comparaison de plusieurs datasets ;
- analyse géographique ;
- prévision simple ;
- intégration d’un modèle Machine Learning ;
- exploitation d’une API Open Data.

## 10. Administration

L’administrateur devra disposer d’un espace spécifique lui permettant de :

- consulter les utilisateurs ;
- gérer les comptes ;
- consulter les datasets disponibles ;
- superviser l’activité générale de la plateforme.

Un dashboard d’administration devra présenter quelques indicateurs globaux concernant l’utilisation de l’application.

## 11. Architecture générale

L’application devra reposer sur une architecture **séparant clairement le Front-end et le Back-end**.

Les technologies principales imposées sont :

### 11.1. Front-end

- React.js ;
- React Router ;
- Hooks ;
- communication avec des API REST.

### 11.2. Back-end

- Node.js ;
- Express.js ;
- API REST.

### 11.3. Base de données

- PostgreSQL recommandé ;
- ou une autre base de données après validation.

## 12. Authentification et sécurité

La plateforme devra mettre en place un système d’authentification.

Les fonctionnalités accessibles devront dépendre du profil de l’utilisateur.

Les équipes devront notamment prendre en compte :

- la protection des mots de passe ;
- la protection des routes ;
- les droits d’accès ;
- la validation des données ;
- la gestion des erreurs.

## 13. Livrables attendus

Chaque groupe devra remettre :

- le code source complet du projet ;
- les scripts ou fichiers nécessaires à la base de données ;
- une documentation synthétique de l’architecture ;
- une documentation de l’API ou une collection Postman ;
- une présentation du projet.

**Le livrable doit être déposé sur la plateforme au plus tard le 25 octobre 2026.**

## 14. Soutenance

La soutenance, prévue **lundi 26 octobre 2026**, devra principalement prendre la forme d’une **démonstration de l’application**.

L’équipe devra présenter :

- le besoin traité ;
- l’architecture retenue ;
- les principales fonctionnalités ;
- le scénario utilisateur ;
- les choix techniques ;
- les difficultés rencontrées et les améliorations envisageables.
