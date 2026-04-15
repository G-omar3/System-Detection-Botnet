# NetWatch SOC

NetWatch SOC est une plateforme Django de detection botnet orientee machine, avec un pipeline hybride combinant regles explicables, machine learning classique et deep learning.

## Structure

- `data/` : jeux de demonstration et scenarios de test
- `ml_model/` : extraction de features, modeles ML, deep learning et moteur hybride
- `dashboard/` : interface Django, endpoints API et assets frontend
- `soc_platform/` : configuration Django
- `exports/` : rapports exportes

## Lancement

```powershell
cd C:\Users\Omarg\Downloads\soc-botnet-analyzer
python manage.py migrate
python manage.py runserver
```

Puis ouvrir `http://127.0.0.1:8000`.

## Tests sans reseau reel

- Cliquer sur `Charger demo` pour charger `data/network_logs_sample.csv`
- Utiliser les autres fichiers de `data/` pour tester des scenarios plus precis
- Utiliser `Demarrer live` en mode `Demo live` pour simuler un flux continu

## Environnement de test local

Un mini-lab de test est disponible dans `test_env/`.

Lancer un scenario live :

```powershell
cd C:\Users\Omarg\Downloads\soc-botnet-analyzer
powershell -ExecutionPolicy Bypass -File .\test_env\run_local_test.ps1 -Scenario mixed
```

Guide complet :

`C:\Users\Omarg\Downloads\soc-botnet-analyzer\test_env\README.md`

Scenarios supplementaires disponibles :

- `normal-office`
- `normal-branch`
- `botnet`
- `ddos-distributed`
- `mixed-enterprise`

## Connexion live

Deux options sont disponibles :

- `Demo live` : relit les scenarios de `data/demo_mixed_lab.csv`
- `UDP collector` : ecoute sur `host:port` et accepte des evenements JSON

Format attendu pour chaque evenement :

- `timestamp`
- `src_ip`
- `dst_ip`
- `dst_port`
- `protocol`
- `bytes_sent`
- `bytes_received`
- `packets`
- `duration`
- `status`
- `dns_query`
- `dns_response_code`

## Rapport

Le dashboard peut exporter :

- un rapport CSV
- un rapport PDF

Le rapport PDF du projet peut etre regenere dans :

`C:\Users\Omarg\Downloads\soc-botnet-analyzer\exports\netwatch_soc_project_report.pdf`
"# System-Detection-Botnet" 
