# Steuerlotse Erica service

> **Important**
**This project has been discontinued**

> **Offener Brief / open letter (2. Oktober 2026)**
Darf ein freies Programm wie „erica“ seine Hersteller-ID und die nötigen ERiC-Laufzeitbibliotheken öffentlich mitliefern?
Die Anfrage an das Bayerische Finanzministerium: [doc/open_letter](doc/open_letter/2026-10-02_hersteller_id_erica.md) — Antwort ausstehend.

🇬🇧
Erica is a service to send tax declarations to ELSTER. 
It is a wrapper around the functionality of ERiC, ELSTER's own client to access their APIs.
It provides functionality to send tax declarations, as well as request, activate and revoke unlock codes.

It was originally [developed as part of the Tech4Germany Fellowship 2020](https://github.com/tech4germany/steuerlotse). 
The fellowship is organized by [DigitalService GmbH des Bundes](https://digitalservice.bund.de).

🇩🇪
Erica ist ein Service, um Steuererklärungen an ELSTER zu senden.
Es dient als Wrapper um die Funktionalität von ERiC, ELSTERs eigener Client um die APIs zu verwenden.
Es stellt Funktionalität zum Absenden von Steuererklärungen sowie dem Beantragen, Freischalten und Stornieren von Freischaltcodes bereit.

Ursprünglich wurde es [als Teil des Tech4Germany Fellowships 2020 entwickelt](https://github.com/tech4germany/steuerlotse), 
das von der [DigitalService GmbH des Bundes](https://digitalservice.bund.de) organisiert wird.

# Contributing

🇬🇧
Everyone is welcome to contribute the development of the _Steuerlotse_. You can contribute by opening pull request, 
providing documentation or answering questions or giving feedback. Please always follow the guidelines and our 
[Code of Conduct](CODE_OF_CONDUCT.md).

🇩🇪  
Jede:r ist herzlich eingeladen, die Entwicklung der _Steuerlotse_ mitzugestalten. Du kannst einen Beitrag leisten, 
indem du Pull-Requests eröffnest, die Dokumentation erweiterst, Fragen beantwortest oder Feedback gibst. 
Bitte befolge immer die Richtlinien und unseren [Verhaltenskodex](CODE_OF_CONDUCT_DE.md). 

## Contributing code
🇬🇧 
Open a pull request with your changes and it will be reviewed by someone from the team. When you submit a pull request, 
you declare that you have the right to license your contribution to the DigitalService and the community. 
By submitting the patch, you agree that your contributions are licensed under the MIT license.

Please make sure that your changes have been tested befor submitting a pull request.

🇩🇪  
Nach dem Erstellen eines Pull Requests wird dieser von einer Person aus dem Team überprüft. Wenn du einen Pull-Request 
einreichst, erklärst du dich damit einverstanden, deinen Beitrag an den DigitalService und die Community zu 
lizenzieren. Durch das Einreichen des Patches erklärst du dich damit einverstanden, dass deine Beiträge unter der 
MIT-Lizenz lizenziert sind.

Bitte stelle sicher, dass deine Änderungen getestet wurden, bevor du einen Pull-Request sendest.

# For Developers 👩‍💻 👨‍💻

## Prerequisites

The following prerequisites must be installed:

- python 3.11
- pipenv
- postgresql client >9.1
- docker and docker-dompose

## Getting started 🛠

### Install Python dependencies

```bash
pipenv install
```

### Download ERiC

Erica uses Pyeric, which is a wrapper around ERiC. For this to work you will need to download the latest ERiC 
library and a test certificate and copy the required files into the source tree.

#### Downloading as a DigitalService employee

You can download binaries and organisation-specific test certificates by running:

```bash
ERICA_BUCKET_NAME=xxx AWS_ACCESS_KEY_ID=xxx AWS_SECRET_ACCESS_KEY=xxx ENDPOINT_URL=xxx pipenv run download-eric
```

Contact the erica service owners for information on how to obtain the required credentials and secrets.


#### Downloading as an external user

 - Download `ERiC-35.2.8.0-Linux-x86_64.jar` (or a newer version) from the [ELSTER developer portal](https://www.elster.de/elsterweb/infoseite/entwickler).
 - Unpack the downloaded jar file
 - Copy the following library files into `erica/worker/lib` such that it matches the given structure:

```bash
$ tree lib
lib
├── libericapi.so
├── libericxerces.so
├── libeSigner.so
└── plugins2
    ├── libcheckElsterDatenabholung.so
    ├── libcheckESt_2021.so
    ├── libcheckGrundsteuerwert.so
    ├── libcheckVaSt.so
    └── libcommonData.so
```

_NOTE_: If you use a Mac, get the corresponding `*.dylib` files

##### Obtain Certificate

You also need to obtain a test certificate from ELSTER and place it under `erica/worker/instances/blueprint/cert.pfx`.

## Developing 👩‍💻 👨‍💻

### Start your docker-compose:
```bash
docker-compose up -d
```

### Run Alembic migration on database:
```
ERICA_ENV=development pipenv run invoke database-migrations
```

### Start the erica API:
```bash
ERICA_ENV=development pipenv run invoke run-api
```
Note: Swagger UI will be available under: http://localhost:8000/docs 

### Start a worker:
```bash
ERICA_ENV=development pipenv run invoke run-worker
```

## Testing 📃

You can run tests as follows:
```bash
pipenv run invoke test
```

If you are missing the ERiC library or a suitable certificate then the respective 
tests will be skipped
