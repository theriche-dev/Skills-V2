# Skills-V2

Skills pour [Claude Code](https://claude.com/claude-code).

## tv-detox : interface TV et télécommande numérique

`.claude/skills/tv-detox/` permet à Claude, via adb, de :

- **refaire l'interface** d'une Android TV / Google TV (écran d'accueil minimal, sans pub) et
  d'enlever le bloatware, avec annulation possible ;
- **piloter la TV depuis ton téléphone** : `python3 .claude/skills/tv-detox/remote/remote.py <IP_TV>`
  affiche une adresse à ouvrir sur le téléphone (même Wi-Fi).

Basé sur [Ansub/tv-detox](https://github.com/Ansub/tv-detox) (MIT, copié dans
`.claude/skills/tv-detox/upstream/`, commit `670a5ab`).

### Utilisation

Claude Code doit tourner **sur un ordinateur du même réseau que la TV** (pas depuis claude.ai ou
l'app mobile, qui ne voient pas ta TV). Installe `adb` (Mac : `brew install android-platform-tools`),
active le débogage USB/réseau sur la TV, puis :

```sh
git clone https://github.com/theriche-dev/Skills-V2.git && cd Skills-V2 && claude
```

et demande par exemple : « Refais l'interface de ma TV Sony Bravia » ou « Lance la
télécommande numérique pour ma TV en 192.168.1.20 ».

Pour l'avoir dans tous tes projets : `cp -r .claude/skills/tv-detox ~/.claude/skills/`.
