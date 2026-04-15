# Scenarios de demonstration

- `network_logs_sample.csv` : jeu principal de test avec trafic mixte.
- `demo_normal.csv` : trafic bureautique normal.
- `demo_normal_office.csv` : postes bureautiques avec SaaS, Teams et navigation classique.
- `demo_normal_branch.csv` : activite normale d'une petite agence.
- `demo_normal_workday.csv` : trafic utilisateur plus proche d'une vraie journee de travail.
- `demo_suspect_recon.csv` : comportement de reconnaissance leger avec echecs reseau et DNS anormal.
- `demo_suspect_dns_anomaly.csv` : activite DNS anormale avec domaines echec et beaconing leger.
- `demo_scanning.csv` : balayage multi-ports et multi-IP.
- `demo_c2_beaconing.csv` : beaconing periodique avec DNS suspect.
- `demo_botnet_multistage.csv` : botnet avec C2, propagation et exfiltration.
- `demo_exfiltration.csv` : gros volume sortant vers une destination unique.
- `demo_propagation.csv` : propagation laterale sur ports SMB.
- `demo_ddos.csv` : rafale de connexions vers une meme cible.
- `demo_ddos_distributed.csv` : plusieurs machines participant a une attaque DDoS.
- `demo_mixed_lab.csv` : laboratoire complet a utiliser avec le mode live demo.
- `demo_mixed_enterprise.csv` : environnement mixte plus riche avec normal, scan, C2, exfiltration, propagation et DDoS.
- `demo_presentation_finale.csv` : scenario de soutenance avec 10 machines, dont 5 normales, 3 suspectes et 2 botnet.
