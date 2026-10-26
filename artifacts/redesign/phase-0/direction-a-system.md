# REGISTRE — proposition A

Système candidat pour Pharma Analyse et Assistant pharmacie. Proposition de phase 0 uniquement ; aucun choix final ni changement de production.

La direction traite l’analyse comme un registre consultable : encre bleue sombre, surfaces blanches réglées par des filets, actions cobalt et typographie compacte. Une navigation horizontale donne une place égale aux trois vues. La hiérarchie vient de l’alignement et de la composition, sans répétition de cartes, gradient ni bandes décoratives latérales.

## Composition

- **Analyse** : source et version au-dessus du travail ; colonne de paramètres de 288 px toujours ouverte sur ordinateur ; graphique HTML large et tableau exact côte à côte avec cette colonne. Sur mobile, le résumé/disclosure de configuration précède les résultats. Changer les paramètres efface le résultat ; Calculer affiche un état CP6 préétabli cohérent.
- **Tableau de bord** : grille analytique large. Moyennes et tableau exact à gauche, effectifs à droite ; complétude et signal IQR dans une seconde rangée. Le filtre Tous/A/B met à jour tous les chiffres concernés via des fixtures prédéfinies. L’IQR conserve explicitement les bornes de la version complète : il ne prétend pas être recalculé par groupe.
- **Assistant** : conversation concise accompagnée d’un dossier structuré : identité, présentation, prix enregistré, date et source. Sur téléphone, le dossier précède la conversation afin de rendre les faits immédiatement lisibles. L’envoi ajoute seulement le texte à l’aperçu et annonce l’absence de requête ; aucun nouveau fait n’est inventé.
- **Système** : spécimens locaux des contrôles, chargement, erreur récupérable et état vide, accessibles par `?view=system`.

## Tokens candidats

| Usage | Valeur |
| --- | --- |
| Encre | `#172b45` |
| Texte secondaire | `#52647a` |
| Action / focus | `#174bcc` |
| Survol primaire | `#123caa` |
| Fond de travail / papier | `#f4f6f9` / `#ffffff` |
| Filets | `#cbd4e1` |
| Information | `#eef3ff` |
| Erreur / avertissement | `#a3272d` / `#775000` |
| Graphique principal / secondaire | `#174bcc` / `#758aa9` |

Segoe UI avec repli sans-serif pour toute l’interface. Corps 16 px, données 14 px, titres de sections 19 px, titre de page 30 px (25 px sur téléphone). Les valeurs du graphique restent à 14–16 px, les graduations HTML à 12 px. Chiffres tabulaires. Échelle d’espacement : 4, 6, 8, 10, 12, 16, 18, 20, 24, 28, 32, 40, 48 px. Contrôles arrondis à 4 px, dialogue à 6 px. Un seul traitement d’élévation, réservé au dialogue.

## Interactions et états

Les boutons, selects, textarea, details et dialogue sont natifs. Le focus est un contour cobalt de 3 px. Le survol modifie le fond et la bordure. Les boutons indisponibles sont visuellement atténués et réellement désactivés. Toute modification des paramètres retire le résultat et désactive Enregistrer jusqu’au calcul suivant. L’action Enregistrer annonce une simulation et ne prétend jamais à une sauvegarde. En quittant une analyse modifiée par la navigation visible, un dialogue permet de rester avec les valeurs en place ou d’abandonner et quitter ; Échap conserve la page.

Les filtres du tableau de bord affichent des résultats préétablis : Tous donne 9 lignes, 8 prix présents, 1 absent, moyenne 51,25 ; A donne 4 lignes, 4 prix présents, aucun absent, moyenne 15 ; B donne 5 lignes, 4 prix présents, 1 absent, moyenne 87,50. Les boutons Inspecter expliquent la définition, Modifier expose un spécimen d’édition clairement annoncé, Enregistrer annonce l’absence de sauvegarde réelle.

L’assistant utilise uniquement l’exemple ABIP 15 mg, boîte de 30 comprimés pelliculés, 372,00 MAD, source AMMPS observée le 18 octobre 2026 ; stock non vérifié. Les prix ne sont pas présentés comme vérifiés aujourd’hui. La conversation temporaire de 30 minutes est expliquée, sans simuler son mécanisme serveur.

Les transitions de largeur des barres durent 180 ms et servent uniquement le changement de filtre. La préférence de réduction du mouvement supprime ces transitions. Aucun chargement de page chorégraphié.

## Responsive et compromis

Seuils : 1100 px pour resserrer la composition ; 900 px pour empiler l’espace de travail ; 600 px pour la composition téléphone, contrôles d’au moins 44 px et paramètres repliés initialement. Les tableaux exacts peuvent défiler dans une région nommée, focalisable, avec indication visible. Les titres et textes longs peuvent revenir à la ligne. Le dossier de présentation est placé avant la conversation sur mobile ; ce choix mérite une évaluation utilisateur lors d’une phase ultérieure.

Cette direction consacre de la hauteur à la méthode et à la provenance. Elle favorise le contrôle analytique et une lecture dense, au prix d’une apparence moins conversationnelle. La navigation horizontale est adaptée à ces trois vues ; l’intégration de toutes les destinations de production demandera un regroupement explicite.

## Limites et vérification

Fichiers autonomes, sans dépendance, actif distant, réseau, stockage, service ou action réelle. La configuration existe uniquement en mémoire dans la page. Les seuls calculs affichés proviennent de fixtures préétablies ; aucune extension du moteur analytique n’est proposée. Les lectures de PRODUCT.md, DESIGN.md, du contrat de contenu et des fixtures CP6/ABIP ont guidé la proposition. Le rendu navigateur et les captures aux tailles demandées sont laissés à l’agent parent ; ce document ne revendique pas de validation visuelle ou d’accessibilité automatisée.

## Compléments proposés pour les états et les graphiques

Succès : `#176346` ; avertissement : `#775000` ; validation/erreur : `#a3272d`. Un succès confirme uniquement une réponse serveur acceptée et nomme l’opération/la révision ; il reste dans le contexte après rafraîchissement du composant. La simulation statique ne revendique pas ce succès. La validation associe un résumé lié, une consigne près du champ, `aria-invalid` et `aria-describedby`, sans effacer la saisie. Un avertissement explique la conséquence en texte. L’issue inconnue demande une vérification en lecture avant toute nouvelle tentative explicite.

Palette catégorielle étendue proposée : `#174bcc`, `#007c83`, `#8b4c9b`, `#8b5c00`, `#a53d4d`, `#3d6d45`, `#5b5f79`, `#805749`. Elle ne remplace pas les valeurs exactes, les marqueurs ou les styles de traits. Les graphiques gardent leurs unités, dénominateurs et omissions. Minimum : axes 12 px, valeurs/tableaux 14 px. La palette complète reste à vérifier dans les vrais graphiques après sélection ; les compositions montrent un nombre réduit de séries. Voir aussi le contrat graphique commun dans INTERACTION_BLUEPRINT.md.

La revue centrale a maintenant rendu et inspecté les prototypes. Les résultats et limites sont consignés dans [REVIEW.md](REVIEW.md), sans approbation du système. Les chemins de source affichent une seule version CP6 disponible dans cet aperçu, sans inventer un catalogue.
