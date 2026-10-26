# TRAVERSE — système candidat B

Proposition Phase 0, non approuvée. Interface de travail locale et autonome. Aucun fichier de production ni système Impeccable n’est modifié.

TRAVERSE donne un repère stable aux trois surfaces : un rail forêt de 184 px et une toile chaude. L’analyse suit une progression horizontale **Source → Question → Résultat → Enregistrer**. Le résultat occupe le grand plan de travail ; les paramètres s’ouvrent à la demande. Les chiffres, la version et les dénominateurs sont la matière visuelle.

## Typographie et tokens

Une seule famille locale : Segoe UI, puis les fontes système sans serif. Corps 15/22,5 px ; titre 30/36 px, 26 px sur mobile ; titres de section 21 px ; contrôles et tableau 14 px ; labels 13 px. L’identité du médicament, la présentation, la source et la date restent à 14 px au minimum. Les axes de graphique sont à 12 px minimum. Les nombres utilisent les chiffres tabulaires. Le monospace est limité aux vrais identifiants et noms de colonnes.

| Usage | Valeur |
|---|---|
| Rail, action principale | Forêt `#173e34` |
| Survol forêt | `#255246` |
| Toile / surface de travail | `#f6f5ef` / `#fffefa` |
| Texte / secondaire | `#203b32` / `#596b60` |
| Séparateurs / contrôles | `#d6ddd3` / `#9eaf9f` |
| Sélection sauge | `#dfe8d7` |
| Barres B / A | `#567451` / `#9aab7d` |
| Avertissement | `#916519`, fond `#f4ead3` |
| Erreur | `#9e3e35`, fond `#fae9e5` |
| Focus | Contour 3 px `#9d6615`, écart 4 px |

Échelle d’espace : 4, 8, 12, 16, 20, 24, 28, 32, 38 et 44 px. Contrôles à 6 px de rayon, plans de travail à 8 px, dialogues et messages à 12 px. Les petites pastilles signalent un état ; elles ne portent pas le contenu principal. Aucune ombre sur les surfaces de travail. Les dialogues et notifications utilisent une ombre neutre décalée. Aucun dégradé ni bande décorative latérale.

## Composition par surface

**Analyse.** Le ruban de contexte garde « TEST CP6 · Observations synthétiques », la version 1, le fichier, les 9 lignes et les 8 colonnes en vue. La question se lit comme une phrase, puis ouvre quatre contrôles natifs. Le grand résultat associe un tracé horizontal lisible à son tableau exact. Le changement d’un paramètre retire immédiatement le résultat obsolète. « Calculer » affiche le preset de test correspondant. L’enregistrement est une action explicite, présentée comme simulation.

Le prix moyen B vaut 87,50 MAD sur quatre prix présents et un manquant ; A vaut 15,00 sur quatre prix présents et zéro manquant. Le tableau développé expose aussi les lignes et les sommes. Les contrôles avancés donnent les règles de moyenne, le zéro présent, les 410 MAD de somme, la moyenne globale 51,25, les extrêmes 0/200 et les bornes IQR −35/105 (Q1 17,5, Q3 52,5). La ligne 008 à 200 est un signal statistique, sans interprétation clinique.

**Tableau de bord.** Une barre de filtres compacte précède deux surfaces asymétriques : moyenne large, effectifs plus étroits. La complétude forme une bande pleine largeur avec taux, dénominateur et effectifs. Les trois widgets ont de vrais chiffres inspectables. Le filtre utilise trois presets cohérents :

| Périmètre | Lignes | Prix présents | Prix manquants | Taux manquant | Moyennes |
|---|---:|---:|---:|---:|---|
| Tous | 9 | 8 | 1 | 11,11 % | B 87,50 ; A 15,00 |
| A | 4 | 4 | 0 | 0,00 % | A 15,00 |
| B | 5 | 4 | 1 | 20,00 % | B 87,50 |

Les proportions des effectifs deviennent 100 % pour le groupe isolé. Le mode de disposition change localement la largeur du premier widget ; le déplacement est une simulation annoncée. Aucun enregistrement de disposition.

**Assistant.** La conversation occupe le centre. Un rail de preuve de 286 px identifie ABIP 15 mg, aripiprazole, boîte de 30 comprimés pelliculés, 372,00 MAD enregistrés, observation AMMPS du 18 octobre 2026 et « Stock non vérifié ». Ces faits restent lisibles sans ouvrir la provenance. La réponse est explicitement issue de `responses.json`, sans nouvelle vérification. La source complète est du texte local, sans lien chargé à distance. Le prix de deux boîtes complètes est un preset à 744,00 MAD. Les autres questions annoncent la limite de la simulation. Les CSV de l’analyste restent distincts du catalogue de l’assistant.

## États et interactions

| Composant | États et comportement |
|---|---|
| Navigation | Défaut léger sur forêt ; survol tonal ; sélection sauge et `aria-current`. Utilitaire de compte distinct en bas. |
| Boutons | Cible minimale 44 px ; survol tonal ; pression plus sombre ; focus ocre ; désactivé neutralisé. Les actions sans backend annoncent leur simulation. |
| Champs | Labels natifs, bordure renforcée au survol, focus commun. La colonne mesurée est désactivée pour le comptage de lignes. Valeur vide dans le compositeur : erreur, `aria-invalid`, focus rendu au champ. |
| Résultat | Prêt : tracé et tableau exact. Modifié : résultat retiré et invitation à recalculer. Les états attente, vide et erreur sont inspectables dans `?view=system`. |
| Onglets | Graphique / tableau avec ARIA ; flèches, Home et End, focus itinérant. |
| Paramètres | Affichage progressif par bouton `aria-expanded`. Valeurs en mémoire pendant la vue. |
| Source et inspection | Dialogues natifs, titre accessible, fermeture par Échap ou bouton. Chiffres exacts adaptés au filtre. |
| Enregistrement | Nom éditable, validation locale ; ne prétend ni sauvegarder, ni partager. Ne supprime pas le statut modifié. |
| Départ avec modifications | Dialogue avec seulement Rester / Abandonner et quitter. Rester et Échap conservent les valeurs ; abandonner permet la navigation. Aucun brouillon récupérable persisté. |
| Assistant | Suite de conversation locale ; détails de source ; question vide refusée ; nouvelle conversation efface les messages locaux et annonce l’absence d’invalidation serveur. |
| Feedback | Notification avec région de statut polie ; erreur rouge brique et consigne de récupération ; avertissement ocre et message explicite. |

Le prototype n’émule pas une indisponibilité de service ou un vrai délai réseau. La vue système montre un squelette de chargement, un résultat vide instructif et un exemple d’erreur de colonne avec récupération. Le délai d’expiration de 30 minutes appartient au produit et est expliqué ; aucune conservation ni expiration réelle n’est revendiquée dans le fichier statique.

## Responsive, accessibilité et mouvement

À 1100 px, le tableau exact passe sous le tracé et les champs passent sur deux colonnes. À 850 px, le rail devient un bandeau forêt : marque et utilitaire séparés, navigation sur la deuxième ligne. À 650 px, formulaires, widgets et conversation passent sur une seule colonne ; la preuve suit la conversation. Le parcours reste une suite compacte de quatre étapes, et les sources continuent à se replier en texte. La marge de toile passe de 38 à 22 puis 17 px. Le tableau exact large dispose d’un défilement horizontal annoncé. Les largeurs de revue demandées sont 1440, 768, 390 et 320 px.

Un lien d’évitement précède l’interface. Les contrôles sont natifs, les dialogues gèrent le focus et Échap, les onglets sont utilisables au clavier, les résultats ont des valeurs textuelles et une alternative tabulaire. La sélection et le curseur de saisie reprennent la palette. Les barres modifient leur largeur en 200 ms avec `cubic-bezier(.16,1,.3,1)` après une action de calcul. Aucun défilé d’entrée. `prefers-reduced-motion` retire les transitions et le défilement animé.

## Portée et compromis

Le fichier autonome offre `?view=analysis`, `?view=dashboard`, `?view=assistant` et `?view=system`, avec retour à `index.html`. Il ne charge aucune dépendance, police distante, service, requête ou stockage. Tout état est en mémoire et disparaît au rechargement. L’affichage « Prototype · données de test · aucune action réelle » reste visible.

La progression calme et la divulgation des paramètres rendent les chiffres prioritaires, au prix d’une ouverture supplémentaire avant édition. Le rail de 184 px donne une orientation constante mais utilise une part de la largeur de bureau. Le rail de preuve rapproche les sources de la réponse, puis s’empile sur mobile.

Les rendus et parcours sont à inspecter par la revue centrale du parent. Aucun essai navigateur n’a été exécuté par l’auteur de cette proposition et aucun résultat de vérification visuelle n’est revendiqué ici.

## Compléments proposés pour les états et les graphiques

Succès : `#255246` ; avertissement : `#71521c` ; validation/erreur : `#9e3e35`. Un succès confirme uniquement une réponse serveur acceptée et nomme l’opération/la révision ; il reste dans le contexte après rafraîchissement du composant. La simulation statique ne revendique pas ce succès. La validation associe un résumé lié, une consigne près du champ, `aria-invalid` et `aria-describedby`, sans effacer la saisie. Un avertissement explique la conséquence en texte. L’issue inconnue demande une vérification en lecture avant toute nouvelle tentative explicite.

Palette catégorielle étendue proposée : `#567451`, `#286b80`, `#8b4c65`, `#906218`, `#325690`, `#6d548f`, `#745746`, `#356864`. Elle ne remplace pas les valeurs exactes, les marqueurs ou les styles de traits. Les graphiques gardent leurs unités, dénominateurs et omissions. Minimum : axes 12 px, valeurs/tableaux 14 px. La palette complète reste à vérifier dans les vrais graphiques après sélection ; les compositions montrent un nombre réduit de séries. Voir aussi le contrat graphique commun dans INTERACTION_BLUEPRINT.md.

La revue centrale a maintenant rendu et inspecté les prototypes. Les résultats et limites sont consignés dans [REVIEW.md](REVIEW.md), sans approbation du système. Les chemins de source affichent une seule version CP6 disponible dans cet aperçu, sans inventer un catalogue.
