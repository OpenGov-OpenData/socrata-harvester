socrata-harvester
=================

A harvester to allow CKAN directories to keep in sync with a Socrata store.

In order to use this tool, you need to have the CKAN harvester extension (https://github.com/okfn/ckanext-harvest)
installed and loaded for your CKAN instance.


Building
------------

To build and use this plugin, simply:

    git clone https://github.com/socrata/socrata-harvester
    cd socrata-harvester
    pip install -r pip-requirements.txt
    pip install ckanclient
    pip install appconfig
    python setup.py develop

Then you will need to update your CKAN configuration to include the new harvester.  This will mean adding the
socrata_harvester plugin as a plugin.  E.g.

    ckan.plugins = harvest ckan_harvester socrata_harvest

[Note]

If error occurred, you may need to install other required packages    

For pylons package, do following:   
    sudo easy_install pylons


Using
------------

After setting this up, you should be able to go to:    
    http://localhost:5000/harvest

And have a new "Socrata" harvest type show up when creating sources.    
    http://localhost:5000/harvest/new

[Note]

If page does not show, check CKAN error log for details(/var/log/apache2/ckan_default.error.log)

Install or fix other required packages

If PasteDeploy reports error, for example: "module has no converters attribute", install PasteDeploy. 
(If it's already installed, deinstall first: pip uninstall PasteDeploy)

    wget https://pypi.python.org/packages/source/P/PasteDeploy/PasteDeploy-1.5.0.tar.gz
    tar -xzvf PasteDeploy-1.5.0.tar.gz
    mv PasteDeploy-1.5.0/ /usr/lib/ckan/default/local/lib/python2.7/site-packages/paste/deploy/
    cd /usr/lib/ckan/default/local/lib/python2.7/site-packages/paste/deploy/PasteDeploy-1.5.0/
    python setup.py develop

Make sure PasteDeploy works fine in python command line:    
    >>> import paste.deploy    
    >>> import paste.deploy.converters    


Running 
------------

In adding new sources page, select Socrata as source type, and fill URL as https://nycopendata.socrata.com/

Now we follow CKAN Harvester process to create run harvest jobs

1. Create job to the source. In command line, do:
    ```
    paster --plugin=ckanext-harvest harvester sources --config=/etc/ckan/default/production.ini
    ```
    Source id: YOUR-SOURCE-ID    
          url: https://nycopendata.socrata.com/    
         type: None    
       active: True    
    owner org: None    
    frequency: MANUAL    
         jobs: 0    
    
    ```
    paster --plugin=ckanext-harvest harvester job YOUR-SOURCE-ID --config=/etc/ckan/default/production.ini
    ```

2. Start gather_consumer job. In command line, do:
    ```
    paster --plugin=ckanext-harvest harvester gather_consumer --config=/etc/ckan/default/production.ini
    ```

3. Start fetch_consumer job. Open 2nd command line, do:
    ```
    paster --plugin=ckanext-harvest harvester fetch_consumer --config=/etc/ckan/default/production.ini
    ```

4. Start running job. Open 3rd command line, do:
    ```
    paster --plugin=ckanext-harvest harvester run --config=/etc/ckan/default/production.ini
    ```


See Results
------------

In CKAN portal, there should be datasets(About 700 more) imported


Contact
------------

Any question/issue/discussion please Email: aziz.igam@ontodia.com
