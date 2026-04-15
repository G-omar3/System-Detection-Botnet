# Environnement de test local

Ce dossier permet de tester SentinelFlux comme un mini-lab reseau, sans infrastructure externe.

## Principe

Le script rejoue un scenario CSV ligne par ligne vers :

- `/api/live/start`
- `/api/live/reset`
- `/api/live/ingest`

Le dashboard recoit alors les evenements comme s'ils arrivaient d'une source reseau en direct.

## Etapes

1. Lancer Django

```powershell
cd C:\Users\Omarg\Downloads\soc-botnet-analyzer
python manage.py runserver
```

2. Ouvrir le dashboard

`http://127.0.0.1:8000`

3. Lancer un scenario live

```powershell
cd C:\Users\Omarg\Downloads\soc-botnet-analyzer
powershell -ExecutionPolicy Bypass -File .\test_env\run_local_test.ps1 -Scenario mixed
```

## Scenarios disponibles

- `normal`
- `normal-office`
- `normal-branch`
- `normal-workday`
- `suspect`
- `suspect-dns`
- `scanning`
- `c2`
- `botnet`
- `exfiltration`
- `propagation`
- `ddos`
- `ddos-distributed`
- `mixed`
- `mixed-enterprise`
- `presentation`

## Exemples

Rejouer un scan reseau plus vite :

```powershell
python .\test_env\replay_live.py --scenario scanning --reset-live --start-live --delay 0.2
```

Rejouer un scenario d'exfiltration en lots de 3 evenements :

```powershell
python .\test_env\replay_live.py --scenario exfiltration --reset-live --start-live --batch-size 3 --delay 0.5
```

Utiliser un CSV personnel :

```powershell
python .\test_env\replay_live.py --file C:\Users\Omarg\Downloads\mon_test.csv --reset-live --start-live
```

## Resultat attendu

Apres le replay :

- les machines apparaissent dans `Vue globale`
- les details montent dans `Machines`
- les alertes se remplissent dans `Alertes`
- le PDF et le CSV peuvent etre exportes a partir des donnees live

## Conseils de validation

- `normal` doit produire peu ou pas d'alertes
- `normal-office` et `normal-branch` doivent rester stables avec des scores bas
- `normal-workday` sert a montrer un trafic utilisateur plus realiste
- `suspect` doit montrer une machine en observation avec quelques alertes mais sans criticite botnet
- `suspect-dns` doit montrer une activite DNS anormale sans passer directement en botnet critique
- `scanning` doit faire monter `distinct_ports`, `failed_connections` et `distinct_destination_ips`
- `c2` doit faire monter `periodicity` et `dns_nxdomain_rate`
- `botnet` doit combiner C2, propagation et exfiltration sur plusieurs machines
- `exfiltration` doit faire monter `bytes_sent` et `upload_download_ratio`
- `propagation` doit faire monter les connexions laterales SMB
- `ddos` doit augmenter `connection_frequency` et `packets`
- `ddos-distributed` doit montrer plusieurs machines offensives contre une meme cible
- `presentation` doit montrer 10 machines avec 5 normales, 3 suspectes et 2 botnet
