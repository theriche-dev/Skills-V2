---
name: tv-detox
description: Nettoyer et accélérer une Android TV / Google TV, remplacer son interface (écran d'accueil minimal TV Detox) et piloter la TV depuis un téléphone ou un ordinateur avec une télécommande numérique, le tout via adb. À utiliser quand l'utilisateur veut refaire l'interface de sa TV, enlever les pubs/bloatware, changer l'écran d'accueil, annuler ces changements, ou créer/lancer une télécommande virtuelle pour sa TV.
---

# TV Detox : interface TV et télécommande numérique

Ce skill emballe le projet open source [Ansub/tv-detox](https://github.com/Ansub/tv-detox)
(licence MIT, copié dans `upstream/`) et y ajoute une télécommande web (`remote/`).

Chemins (relatifs à ce fichier) :

- `upstream/` : le projet d'origine. Scripts : `supports.sh`, `candidates.sh`, `install.sh`,
  `check.sh`, `undo.sh`, `build.sh`. Règles de nettoyage : `upstream/docs/debloat.md`.
  Toute la FAQ par marque (TCL, Philips, Sony, OnePlus, Chromecast…) : `upstream/README.md`.
- `remote/remote.py` + `remote/remote.html` : télécommande numérique.

## Avant tout : où ça doit tourner

adb doit atteindre la TV sur le réseau local. Ce skill ne marche donc que si Claude Code tourne
**sur un ordinateur connecté au même réseau (Wi-Fi ou Ethernet) que la TV**. Depuis une session
cloud (claude.ai/code, app mobile), la TV est injoignable : dis-le à l'utilisateur et propose-lui
d'ouvrir ce dépôt dans Claude Code sur son ordinateur. Ne prétends jamais avoir agi sur la TV.

Prérequis sur l'ordinateur : `adb` (Mac : `brew install android-platform-tools` ; Windows/Linux :
[platform-tools](https://developer.android.com/tools/releases/platform-tools), sous Windows lancer
les `.sh` depuis Git Bash) et Python 3 pour la télécommande.

Compatibilité : Android TV et Google TV (Sony, TCL, Hisense, Philips, Xiaomi, OnePlus, Nvidia
Shield, Chromecast with Google TV…). Fire TV : nettoyage oui, écran d'accueil non. Roku, Samsung
(Tizen), LG (webOS) : non, ce ne sont pas des Android.

## 1. Connecter la TV

1. Sur la TV : Paramètres → Préférences de l'appareil (ou Système) → À propos → appuyer 7 fois
   sur **Build**. Puis Options pour les développeurs → activer **Débogage USB** (et
   **Débogage réseau** / **Débogage sans fil** s'il existe).
2. Trouver l'IP de la TV (Paramètres → Réseau) puis `adb connect <IP>:5555`. La TV demande
   « Autoriser le débogage ? » : cocher « Toujours autoriser » puis **Autoriser**.
3. Chromecast / Google TV récentes (débogage sans fil seulement) : « Associer un appareil avec un
   code », `adb pair <IP>:<port d'association>`, puis `adb connect <IP>:<port affiché>` et utiliser
   cette adresse `<IP>:<port>` dans tous les scripts. Le port change à chaque redémarrage.

## 2. Diagnostiquer (ne change rien)

```sh
sh upstream/supports.sh <TV>      # modèle, Android, RAM, launchers possibles, conseil
sh upstream/candidates.sh <TV>    # chaque app avec un verdict : never / keep / safe / review
adb -s <TV> shell cat /proc/meminfo | head -3   # mémoire libre, à noter avant/après
```

## 3. Nettoyer (bloatware, pubs) : seulement si l'utilisateur le demande

Lis `upstream/docs/debloat.md` avant. Règles impératives :

- **Avant tout changement**, explique en mots simples le risque (quelques TV sont restées bloquées
  sur le logo ou en boucle de redémarrage ; tu peux te tromper) et demande confirmation.
- Liste chaque app en français clair : sans risque à désactiver / nécessaire à la TV / apps
  utilisées. **Demande avant chaque désactivation.**
- Désactiver, jamais désinstaller : `adb -s <TV> shell pm disable-user --user 0 <package>`.
  Tiens une liste d'annulation (une ligne par changement, ex. `off com.example.app`) et donne-la
  à l'utilisateur ; `pm enable <package>` annule.
- **Ne jamais désactiver** : Google Play services (`com.google.android.gms`), Play Store,
  Paramètres, System UI, apps de configuration, clavier, Bluetooth, entrées HDMI, framework
  d'entrées/tuner TV, ce qui est marqué `never` ou `PERSISTENT`, l'app propriétaire du Wi-Fi
  (règle 5 de debloat.md). Sur Google TV / Chromecast, ne pas désactiver
  `com.google.android.apps.tv.launcherx`. Dans le doute, laisser activé.
- Après la dernière modification : attendre 30 s, redémarrer une fois (`adb -s <TV> reboot`),
  vérifier que la TV démarre normalement, comparer la mémoire libre avant/après.

## 4. Refaire l'interface (écran d'accueil TV Detox)

Un écran unique, sans pub ni compte, ~30 Mo de RAM : les apps choisies, les entrées HDMI, une
horloge, un fond dégradé.

```sh
sh upstream/install.sh <TV>                                   # apps choisies automatiquement
sh upstream/install.sh <TV> "com.netflix.ninja,com.google.android.youtube.tv"
sh upstream/install.sh <TV> "" "bluetooth,sound,picture"      # raccourcis à côté de l'horloge
CLOCK=24 sh upstream/install.sh <TV>                          # horloge 24 h (12, 24, auto)
GOOGLE_TV=1 sh upstream/install.sh <TV>                       # Google TV : remplace aussi l'accueil Google (risqué, seulement si reconnexion USB/5555 possible)
```

`install.sh` télécharge le dernier APK publié (ou utilise `upstream/out/tvhome.apk` s'il a été
compilé), l'installe, propose de désactiver l'ancien launcher et vérifie que Home ouvre le nouveau.
Pour trouver un nom de package : `adb -s <TV> shell pm list packages | grep -i <nom>`.

Personnalisation sur la TV, avec la télécommande : appui long sur OK (ou Menu) sur une tuile pour
déplacer / remplacer / retirer / renommer une entrée HDMI ; tuile **Ajouter une app** ; tuile
**Paramètres → Fond d'écran** (14 dégradés).

Personnalisation plus profonde (couleurs, disposition, nouvelles tuiles) : c'est du Java simple,
sans Gradle, dans `upstream/src/com/ansub/tvhome/` (`MainActivity.java` pour l'écran,
`Strings.java` pour les traductions). Compiler avec `sh upstream/build.sh` (Java 17 + Android SDK
platform 34 / build-tools 34.0.0), puis relancer `install.sh` qui prendra `out/tvhome.apk`.
Garder `upstream/key.jks` créé au premier build (les mises à jour doivent être signées avec la
même clé ; il est ignoré par git, ne pas le committer). Tester : `sh upstream/ci/smoke-test.sh <TV>`.

Vérifier / réparer après une mise à jour de la TV : `sh upstream/check.sh <TV> [--fix] [liste.txt]`.

## 5. Télécommande numérique

```sh
python3 remote/remote.py                 # trouve la TV tout seul (adb déjà connecté, sinon scan du port 5555)
python3 remote/remote.py <TV>            # ou --port 9000, --host 127.0.0.1
python3 remote/remote.py <TV> --probe    # marque, modèle, Android, Android TV ou non, launcher, entrées HDMI
```

Si adb manque, le script télécharge une fois les platform-tools officiels de Google dans
`~/.tv-remote` : il suffit de Python 3. Commence par `--probe` sur une TV inconnue pour savoir quoi adapter. Le script se connecte à la
TV, puis affiche une URL du type `http://192.168.1.20:8765/?t=<jeton>`.
L'utilisateur l'ouvre sur son téléphone (même Wi-Fi) ou dans le navigateur de l'ordinateur et
peut l'ajouter à l'écran d'accueil du téléphone. Elle offre : croix directionnelle + OK (appui
long = menu des tuiles TV Detox) ou pavé tactile (glisser = flèches, toucher = OK), Retour,
Accueil, Menu, Marche/Arrêt, Source, Réglages, Recherche, volume et chaînes (maintien =
répétition), lecture/pause/avance/retour, Muet, chiffres 0-9, Info, chaîne précédente, touches
couleur, HDMI 1/2/3, TV, AV, Guide, envoi de texte (ASCII seulement : les accents sont retirés), et
lancement des apps installées (avec leur nom). Un voyant indique si la TV répond ; le serveur se
reconnecte tout seul après un redémarrage de la TV. Les touches passent par un shell adb
permanent pour plus de réactivité. Depuis un ordinateur, les
flèches, Entrée, Échap/Retour arrière, `h`, `m`, espace, `+`, `-`, `0` fonctionnent aussi.

Sécurité : seules les touches de la liste blanche de `remote.py` peuvent être envoyées ; chaque
requête exige le jeton aléatoire de l'URL (jeton fixe possible avec `--token` ou `REMOTE_TOKEN`).
Pour l'étendre (nouvelle touche, raccourci vers une app), ajouter le `KEYCODE_` dans `KEYS` et un
bouton `data-key` dans `remote.html`. Tester ensuite avec un faux `adb` ou un émulateur.

La télécommande a besoin du débogage adb activé : rappelle à l'utilisateur que pendant ce temps
d'autres appareils du réseau peuvent demander à contrôler la TV.

### Star Track (ex. ST-43D-MT2200-SMART) et autres « Smart TV » Android génériques

Marque vendue surtout aux Émirats / en Afrique ; pas de fiche officielle trouvée pour ce modèle.
Les fiches revendeurs du 43" parlent d'Android (souvent un Android « téléphone » non certifié
Android TV, avec tuner DVB-T2/S2). À vérifier avec `--probe`. Connectique vue sur la TV de
l'utilisateur : 3 HDMI, AV composite (jaune/blanc/rouge), Ethernet, 2 USB, sortie audio coaxiale,
antenne et satellite. Écran « Infos système » de cette TV : Android 13, 1 Go de RAM, modèle
`SMART_TV`, firmware `20240126_110242`, 4 cœurs, GPU Mali-G31. C'est un menu maison, pas les
Paramètres Android : « Numéro de build » n'y apparaît pas. Avec 1 Go, le nettoyage (section 3)
aide beaucoup ; voir aussi la note « TCL 32S4K » (954 Mo) dans `upstream/README.md`.
Points à connaître :

- Ethernet : brancher un câble rend la connexion adb bien plus stable que le Wi-Fi.

- Mode développeur : Paramètres → (Système / Préférences) → À propos → 7 appuis sur **Numéro de
  build** / **Version**. Sur l'écran maison « Infos système », essayer 7 appuis sur **Version
  Android** puis sur **Version Firmware** (message « Vous êtes développeur »). Si l'écran de réglages TV n'a pas d'Options développeur, ouvrir l'app
  « Paramètres » Android (`com.android.settings`) depuis la liste des apps. Activer le **débogage
  USB** et, s'il existe, **ADB par réseau** (port 5555). Note l'IP de la TV (Paramètres → Réseau).
- **Marche/Arrêt** : éteint la TV, mais en veille le Wi-Fi est en général coupé, donc la rallumer
  par le réseau ne marche souvent pas (utiliser la télécommande physique).
- HDMI 1/2/3 (`KEYCODE_TV_INPUT_HDMI_n`), AV (`KEYCODE_TV_INPUT_COMPOSITE_1`), Guide, touches couleur : dépend du firmware. Si rien ne
  se passe, utiliser **Source**. Pour une touche maison inconnue, demander à l'utilisateur
  d'appuyer dessus pendant `adb shell getevent -lt` pour lire son code.
- Si `--probe` dit « plain Android », les apps sont listées via `LAUNCHER` (pas `LEANBACK`) et
  l'écran d'accueil TV Detox est fait pour une TV : il fonctionne, mais vérifier que Home l'ouvre.

## 6. Annuler / dépanner

```sh
sh upstream/undo.sh <TV>                                  # remet l'accueil d'origine, retire TV Detox
adb -s <TV> shell pm list packages -d                     # tout ce qui est désactivé
adb -s <TV> shell pm enable <package>                     # réactiver une app
```

TV bloquée en redémarrage : la connexion adb passe souvent quelques secondes à chaque démarrage ;
`adb connect <IP>` puis `adb wait-for-device`, puis réactiver tout ce qui est désactivé (voir
« My TV is stuck restarting » dans `upstream/README.md`). Pour tout cas par marque, chercher dans
`upstream/README.md`.

## 7. À la fin

Rappeler de couper **Débogage USB**, **réseau** et **sans fil** (ou les Options développeurs) une
fois fini, et de ne les rallumer que pour `undo.sh`, une mise à jour ou la télécommande. Sur une
TV OLED, garder l'économiseur d'écran actif (risque de marquage).
