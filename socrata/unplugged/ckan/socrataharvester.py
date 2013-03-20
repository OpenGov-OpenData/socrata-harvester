import urllib2

from ckan.lib.base import c
from ckan import model
from ckan.model import Session, Package
from ckan.logic import ValidationError, NotFound, get_action
from ckan.lib.helpers import json

from ckanext.harvest.model import HarvestJob, HarvestObject, HarvestGatherError, \
                                    HarvestObjectError

from ckanclient import CkanClient

import logging
log = logging.getLogger('socrata')

from ckanext.harvest.harvesters.base import HarvesterBase
from socrata.unplugged.socrataAdaptor import socrataAdaptor

class SocrataHarvester(HarvesterBase):
    '''Harvests datasets from Socrata

    This harvester is meant to take dataset references from Socrata and push them into a CKAN instance.

    This works through a two step process:
        1)  Get the list of datasets by pulling down the DCAT catalog of all datasets
        2)  Then, pull down additional metadata through the Socrata SODA API for each view

    From there, it is able to build the appropriate records for importing.
    '''

    config = None
    api_version = '2'

    def _get_dcat_endpoint(self):
        return '/api/dcat.rdf'

    def _set_config(self,config_str):
        if config_str:
            self.config = json.loads(config_str)

            if 'api_version' in self.config:
                self.api_version = self.config['api_version']

            log.debug('Using config: %r', self.config)
        else:
            self.config = {}

    def info(self):
        return {
            'name': 'socrata',
            'title': 'Socrata',
            'description': 'Harvests remote Socrata datasets',
            'form_config_interface':'Text'
        }

    def validate_config(self,config):
        if not config:
            return config

        try:
            config_obj = json.loads(config)

            if 'default_tags' in config_obj:
                if not isinstance(config_obj['default_tags'],list):
                    raise ValueError('default_tags must be a list')

            if 'default_groups' in config_obj:
                if not isinstance(config_obj['default_groups'],list):
                    raise ValueError('default_groups must be a list')

                # Check if default groups exist
                context = {'model':model,'user':c.user}
                for group_name in config_obj['default_groups']:
                    try:
                        group = get_action('group_show')(context,{'id':group_name})
                    except NotFound,e:
                        raise ValueError('Default group not found')

            if 'default_extras' in config_obj:
                if not isinstance(config_obj['default_extras'],dict):
                    raise ValueError('default_extras must be a dictionary')

            if 'user' in config_obj:
                # Check if user exists
                context = {'model':model,'user':c.user}
                try:
                    user = get_action('user_show')(context,{'id':config_obj.get('user')})
                except NotFound,e:
                    raise ValueError('User not found')

            for key in ('read_only','force_all'):
                if key in config_obj:
                    if not isinstance(config_obj[key],bool):
                        raise ValueError('%s must be boolean' % key)

        except ValueError,e:
            raise e

        return config


    def gather_stage(self,harvest_job):
        log.debug('In SocrataHarvester 2 gather_stage (%s)' % harvest_job.source.url)
        get_all_packages = True

        dcatUrl = "%s/api/dcat.rdf" % harvest_job.source.url.rstrip('/')
        log.debug(dcatUrl)

        adaptorInstance = socrataAdaptor()
        package_ids = adaptorInstance.listDatasetIds(dcatUrl)

        try:
            object_ids = []
            if len(package_ids):
                for package_id in package_ids:
                    # Create a new HarvestObject for this identifier
                    obj = HarvestObject(guid = package_id, job = harvest_job)
                    obj.save()
                    object_ids.append(obj.id)

                return object_ids

            else:
                self._save_gather_error('No packages received for URL: %s' % url,
                    harvest_job)
                return None
        except Exception, e:
            self._save_gather_error('%r'%e.message,harvest_job)


    def fetch_stage(self,harvest_object):
        '''
        Fetches the list of datasets from the catalog
        '''
        log.debug('In SocrataHarvester fetch_stage')

        self._set_config(harvest_object.job.source.config)

        fetchUrl = "%s/api/views/%s.xml" % (harvest_object.source.url.rstrip('/'), harvest_object.guid)
        log.debug(fetchUrl)


        try:
            response = urllib2.urlopen(fetchUrl)
            content = response.read()

        except Exception, e:
            log.exception('Could not load ' + fetchUrl)
            self._save_gather_error('%r'%e.message,harvest_object)


        # Save the fetched contents in the HarvestObject
        harvest_object.content = content
        harvest_object.save()

        #log.debug(content)
        return True

    def import_stage(self,harvest_object):
        '''
        Imports each dataset from Socrata, into the CKAN server
        '''
        log.debug('In SocrataHarvester import_stage')
        if not harvest_object:
            log.error('No harvest object received')
            return False

        if harvest_object.content is None:
            self._save_object_error('Empty content for object %s' % harvest_object.id,
                    harvest_object, 'Import')
            return False

        self._set_config(harvest_object.job.source.config)

        log.debug(harvest_object.job.source.config)
        try:
            #log.debug(harvest_object.content)

            d = socrataAdaptor()
            log.debug("Converting View")
            package_dict = d.convertViewXml(harvest_object.id, harvest_object.source.url.rstrip('/'), harvest_object.content)
            log.debug(package_dict)

            # Set default tags if needed
            default_tags = self.config.get('default_tags',[])
            if default_tags:
                if not 'tags' in package_dict:
                    package_dict['tags'] = []
                package_dict['tags'].extend([t for t in default_tags if t not in package_dict['tags']])


            # Set default groups if needed
            default_groups = self.config.get('default_groups',[])
            if default_groups:
                if not 'groups' in package_dict:
                    package_dict['groups'] = []
                package_dict['groups'].extend([g for g in default_groups if g not in package_dict['groups']])

            log.debug(package_dict)

            result = self._create_or_update_package(package_dict,harvest_object)
            #log.debug(result)

            if result and self.config.get('read_only',False) == True:
                package = model.Package.get(package_dict['id'])

                # Clear default permissions
                model.clear_user_roles(package)

                # Setup harvest user as admin
                user_name = self.config.get('user',u'harvest')
                user = model.User.get(user_name)
                pkg_role = model.PackageRole(package=package, user=user, role=model.Role.ADMIN)

                # Other users can only read
                for user_name in (u'visitor',u'logged_in'):
                    user = model.User.get(user_name)
                    pkg_role = model.PackageRole(package=package, user=user, role=model.Role.READER)



        except ValidationError,e:
            self._save_object_error('Invalid package with GUID %s: %r' % (harvest_object.guid, e.error_dict),
                    harvest_object, 'Import')
        except Exception, e:
            self._save_object_error('%r'%e,harvest_object,'Import')


