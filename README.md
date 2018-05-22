# local deploy script

Simple script to deploy Java applications. 

#### Exec
```bash
# python ldeploy.py latest_build chuck-api
```

#### Requirements

* Application directory structure:

```
/opt/chuck/chuck-api
├── archive
│   ├── chuck-api-1.jar
│   └── chuck-api-2.jar
├── current
│   └── chuck-api.jar -> /opt/chuck/chuck-api/latest/chuck-api-4.jar
├── latest
│   ├── chuck-api-3.jar
│   └── chuck-api-4.jar
└── logs
    ├── spring.log
    ├── spring.log-2018-02-23.0.log.gz
    ├── spring.log-2018-02-24.0.log.gz
    └── spring.log-2018-02-25.0.log.gz
```
    
* Environment file:
```
# /etc/default/chuck-api (sample)

APP_ROOT=/opt/chuck/chuck-api
BINARY="chuck-api.jar"
PORT="23000"
USER="chuck"
JAVA_OPTS="-Xmx128m"
CONFIG_SERVER="-Dspring.cloud.config.uri=http://config-chuck-api.chuck.int:10000"
LOGGING="-Dlogging.config=/etc/logback-spring.xml -Dlogging.path=/opt/chuck/chuck-api/logs"
```

* Systemd service file 
```
# /etc/systemd/system/chuck-api.service (sample)

[Unit]
Description=chuck-api
After=syslog.target

[Service]
EnvironmentFile=-/etc/default/chuck-api
WorkingDirectory=/opt/chuck/chuck-api/current
User=chuck
ExecStart=/usr/bin/java -Duser.timezone=UTC $LOGGING $CONFIG_SERVER $JAVA_OPTS -Dserver.port=${PORT} -jar $BINARY
StandardOutput=journal
StandardError=journal
SyslogIdentifier=chuck-api
SuccessExitStatus=143

[Install]
WantedBy=multi-user.target
```

#### Further info

[Running Spring Boot applications as systemd services on Linux](https://medium.com/@manjiki/running-spring-boot-applications-as-system-services-on-linux-5ea5f148c39a)

