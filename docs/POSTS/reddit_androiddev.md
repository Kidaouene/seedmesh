# r/androiddev — NE PAS POSTER MAINTENANT
- Vérifié : le sub n'autorise généralement **pas l'auto-promotion**. La seule exception est le thread mensuel **« Interesting Android Apps: <mois> Showcase »**, destiné aux projets **Android natifs**, avec mention du modèle économique (gratuit, payant…).
- SeedMesh n'a aujourd'hui **pas d'app ni d'AAR Android** : il tourne dans Termux. Un post maintenant serait hors sujet (règle 1 : développement d'applications Android).
- Ce brouillon est à poster **comme commentaire dans le showcase mensuel**, une fois l'AAR ou l'app de démo publiée :

> **SeedMesh (free, Apache-2.0, no ads/tracking)** — https://github.com/Kidaouene/seedmesh
> AI disclosure: built with heavy AI assistance, reviewed and tested by me.
> On-device response cache for local LLM inference: llama.cpp via JNI, foreground service (declared FGS type), AIDL + ContentProvider behind a signature permission, no open TCP port, per-app storage excluded from backups. Repeated prompts return from SQLite instead of re-running inference (89 ms vs ~4 s measured on desktop; phone numbers: <À MESURER>). Looking for feedback on the service/IPC design.
