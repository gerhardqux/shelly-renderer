Shelly renderer for Salt
========================

Create salt states with a shell like syntax.

.. image:: https://travis-ci.org/gerhardqux/shelly-renderer.svg?branch=master
       :target: https://travis-ci.org/gerhardqux/shelly-renderer

States are commonly written in yaml, which is easy,
but places a limit on functionality and flexibility.
To gain more functionality and flexibility, you can template your yaml
using jinja2, at the cost of easyness. You can go one step further, and
obtain maximum functionality and flexibility by writing your states in python.
This is even more difficult.

Salt encourages simplicity and thus suggests you gravitate down to yaml as much
as possible.

Shelly embraces this gravity and trades even more functionality and
flexibility for ease and simplicity.

Having said that, shelly is no shell, and one soon hits its limits.
Instead of adding functionality to shelly, you are encouraged to move up
to yaml+jinja in all but the most basic situations.

Shelly expects imperative form (e.g. install this package) instead of
declarative form (e.g. this package should be installed). This is really
an illusion for the user who is accustomed to shell scripts. Every line
is translated to a declarative datastructure anyway.

Examples
--------

Install influxdb.

.. code-block:: bash

    #!shelly

    yum install -y influxdb
    mkdir -m 0755 /var/lib/influxdb
    chown influxdb:influxdb /var/lib/influxdb

    curl salt://influxdb/files/config.toml.jinja | jinja > /etc/influxdb/config.toml
    chown root:root /etc/influxdb/config.toml
    chmod 0644 /etc/influxdb/config.toml

    useradd -d /opt/influxdb -s /bin/bash -c InfluxDBServiceUser influxdb

    systemctl start influxdb
    systemctl enable influxdb

That's all. Nice, and concise.


TODO
----

missing:

 * for loops
 * cfg dict from pillar
 * if statements
 * examples
 * pydoc
 * sane pipe renderer
