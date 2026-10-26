# Cahier — système candidat C

Proposition isolée de phase 0, sans adoption du système. Elle utilise Impeccable en mode Operate. Le contexte produit et le contrat de contenu gouvernent les faits ; DESIGN.md reste un relevé de l’existant.

Le travail ressemble à un rapport analytique manipulable. La source figée, la définition du calcul et les résultats se suivent dans une lecture verticale. Une navigation principale haute et mince puis des onglets de document remplacent la navigation latérale. Les titres Cambria/Georgia restent petits ; les contrôles et données utilisent Segoe UI. Aucun grand titre éditorial, texture papier, dégradé ou bande décorative.

## Tokens

| Rôle | Valeur |
| --- | --- |
| Papier / fond secondaire | `#fffefa` / `#f3f1eb` |
| Encre / texte secondaire | `#252822` / `#62665e` |
| Règle / contour de contrôle | `#d4d4c9` / `#909387` |
| Action / survol | `#792f37` / `#62232b` |
| Donnée secondaire | `#866018` |
| Focus / succès / erreur | `#1b5975` / `#365b42` / `#972e2e` |
| Rayon contrôle / dialogue | 3 px / 6 px |
| Largeur document / consultation | 1 240 px / 920 px |

Les espaces suivent 4, 8, 12, 16, 18, 20, 24, 28, 32, 40, 48 et 56 px. Les règles servent à délimiter les sections et aligner les données. Seul le dialogue a une ombre (`0 15px 55px #25282230`).

## Typographie et composants

Corps Segoe UI, system-ui, sans-serif : 15 px, interligne 1,55. Titres Cambria, Georgia, serif : graisse 600 et approche −0,01 em. H1 30 px (27 px sur petit écran), h2 23 px, h3 19 px. Contrôles/données 14 px, labels et contexte 13 px. Les nombres utilisent des chiffres tabulaires ; les légendes restent en HTML lisible.

Les formulaires utilisent des labels visibles et des contrôles natifs. Le bouton principal est oxblood plein ; les actions secondaires ont un contour neutre. Les tableaux ont des en-têtes sobres, des nombres alignés à droite et un défilement contenu lorsque nécessaire. Les graphiques en barres HTML ont une alternative exacte à côté. Les détails de source et de méthode utilisent `details/summary`.

Les états survol, focus, actif et désactivé sont définis. Focus : contour bleu de 3 px décalé de 3 px. La sélection du texte et le curseur reprennent la palette. Les résultats obsolètes sont retirés dès modification d’un réglage. Le calcul présente un court état d’attente local. Le spécimen facultatif `?view=system` montre aussi une erreur et un état vide explicitement nommés exemples. La confirmation native propose uniquement « Rester » et « Abandonner » ; Échap conserve le contexte.

## Trois surfaces

- `?view=analysis` : bande source/version, réglages horizontaux, résultat graphique et tableau exact puis méthodes. Moyenne et somme utilisent des résultats prédéfinis de la fixture. Le choix tableau seul fonctionne. La version reste figée. Les changements non enregistrés déclenchent une confirmation avant de quitter par les liens du prototype.
- `?view=dashboard` : trois sections de rapport montrent moyennes, nombres de lignes et complétude. Le filtre tous/A/B met à jour tous les chiffres concernés à partir de presets. « Inspecter » révèle les règles. « Modifier la disposition » expose des boutons pour déplacer les sections en mémoire. Le contexte du périmètre est affiché à côté.
- `?view=assistant` : question contextualisée, identité ABIP 15 mg, boîte de 30 comprimés pelliculés, tableau de faits, source AMMPS du 18 octobre 2026 puis question suivante. Le stock reste non vérifié. La suite prévue « deux boîtes » montre 744,00 MAD et s’annonce comme simulation. Les autres questions ne sont pas interprétées et n’obtiennent pas de fausse réponse. Réinitialiser retire le contexte à l’écran avec confirmation ; le bouton de recharge restaure l’exemple local.

Tous les boutons d’enregistrement annoncent une simulation et ne prétendent jamais à une sauvegarde. Aucun appel réseau, dépendance, stockage, inférence, service ou modification d’application. Les changements survivent seulement dans la page en mémoire.

## Responsive et mouvement

À 1 000 px les marges se resserrent ; les contenus des sections du tableau se superposent. À 760 px le résultat de l’analyse se superpose, la bande source passe à deux colonnes et le contexte du tableau suit le rapport. À 480 px les graphiques du tableau se superposent, le compositeur et les actions occupent la largeur utile et les cibles atteignent 44 px. À 320 px la configuration garde deux colonnes de champs courts ; les métadonnées reviennent à la ligne et les tableaux contiennent leur défilement.

Aucune animation d’entrée. Les changements de couleur durent 160 ms ; la simulation de calcul attend 350 ms pour rendre son état visible. `prefers-reduced-motion` supprime transitions, animations et défilement doux.

## Différences et compromis

Cahier met la lecture, la comparaison et la vérification avant la densité d’un poste de configuration permanent. L’analyse est un document continu ; le tableau est une matrice de lectures avec contexte, sans collection de tuiles KPI. L’assistant ressemble à un relevé de consultation construit par la conversation. Cela demande davantage de défilement vertical et convient moins à des ajustements simultanés de nombreuses options. L’expressivité se concentre dans les titres, les alignements et le rythme des sections.

Le fichier a été contrôlé statiquement lors de sa création. La vérification visuelle et les essais navigateur sont confiés à l’agent principal ; aucun résultat de QA visuelle n’est revendiqué ici.

## Compléments proposés pour les états et les graphiques

Succès : `#365b42` ; avertissement : `#866018` ; validation/erreur : `#972e2e`. Un succès confirme uniquement une réponse serveur acceptée et nomme l’opération/la révision ; il reste dans le contexte après rafraîchissement du composant. La simulation statique ne revendique pas ce succès. La validation associe un résumé lié, une consigne près du champ, `aria-invalid` et `aria-describedby`, sans effacer la saisie. Un avertissement explique la conséquence en texte. L’issue inconnue demande une vérification en lecture avant toute nouvelle tentative explicite.

Palette catégorielle étendue proposée : `#792f37`, `#866018`, `#1b5975`, `#765284`, `#3a5c91`, `#365b42`, `#815941`, `#51565e`. Elle ne remplace pas les valeurs exactes, les marqueurs ou les styles de traits. Les graphiques gardent leurs unités, dénominateurs et omissions. Minimum : axes 12 px, valeurs/tableaux 14 px. La palette complète reste à vérifier dans les vrais graphiques après sélection ; les compositions montrent un nombre réduit de séries. Voir aussi le contrat graphique commun dans INTERACTION_BLUEPRINT.md.

La revue centrale a maintenant rendu et inspecté les prototypes. Les résultats et limites sont consignés dans [REVIEW.md](REVIEW.md), sans approbation du système. Les chemins de source affichent une seule version CP6 disponible dans cet aperçu, sans inventer un catalogue.
