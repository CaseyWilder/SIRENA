import json
import os
import sys
from os import path

import requests
from requests.auth import HTTPBasicAuth


class SonarNovobi():

    def __init__(self):
        super().__init__()

        self.host_url = 'https://sonarqube.novobi.com'

        # Permissions
        self.dev_permissions = ['user', 'codeviewer', 'issueadmin']
        self.lead_permissions = [
            'user', 'codeviewer', 'issueadmin', 'admin', 'securityhotspotadmin', 'scan']

        # Initial variables
        self.sonar_token = ''
        self.github_token = ''
        self.project_key = ''
        self.repo_collaborators = []
        self.sonar_users_list = []
        self.lead_users_list = []

        # Map user name:
        self.format_user_name = {
            'lee': 'leelou',
            'nguyen': 'nguyenhoang'
        }

    def get_repo_collaborators(self):
        api_url = 'https://api.github.com/repos/novobi1/' + \
            self.project_key + '/collaborators'
        headers = {'Authorization': 'token ' + self.github_token}
        result = requests.get(api_url, headers=headers).json()
        for collaborator in result:
            self.repo_collaborators.append(collaborator['login'])

    def get_sonar_users_list(self):
        api_url = self.host_url + '/api/users/search'
        users_list_json = self.send_api_request(
            api_url, 'get', self.sonar_token).json()
        for user_info in users_list_json['users']:
            self.sonar_users_list.append(user_info['login'])

    def create_user_group(self, user_type):
        if not self.check_user_group(user_type):
            url = self.host_url + '/api/user_groups/create'
            group_name = '?name=' + self.project_key + '-' + user_type
            api_url = url + group_name
            self.send_api_request(api_url, 'post', self.sonar_token)
            self.add_permissions_to_group(user_type)

    def check_user_group(self, user_type):
        api_url = self.host_url + '/api/user_groups/search'
        group_name = self.project_key + '-' + user_type
        groups_list_json = self.send_api_request(
            api_url, 'post', self.sonar_token).json()['groups']
        for group in groups_list_json:
            if group_name == group['name']:
                return True
        return False

    def add_permissions_to_group(self, user_type):
        url = self.host_url + '/api/permissions/add_group'
        group_name = '?groupName=' + self.project_key + '-' + user_type
        project_key = '&projectKey=' + self.project_key

        if user_type == 'dev':
            permissions_list = self.dev_permissions
        elif user_type == 'lead':
            permissions_list = self.lead_permissions

        for each_permission in permissions_list:
            permission = '&permission=' + each_permission
            api_url = url + group_name + permission + project_key
            self.send_api_request(api_url, 'post', self.sonar_token)

    def add_user_to_group(self, user_login, user_type):
        url = self.host_url + '/api/user_groups/add_user'
        user = '?login=' + user_login
        group_name = '&name=' + self.project_key + '-' + user_type
        api_url = url + user + group_name
        self.send_api_request(api_url, 'post', self.sonar_token)

    def remove_user_in_group(self, user_login, user_type):
        url = self.host_url + '/api/user_groups/remove_user'
        user = '?login=' + user_login
        group_name = '&name=' + self.project_key + '-' + user_type
        api_url = url + user + group_name
        self.send_api_request(api_url, 'post', self.sonar_token)

    def format_repo_collaborator(self, collaborator):
        if collaborator in self.format_user_name.keys():
            return self.format_user_name[collaborator]
        return collaborator

    def set_dev_group_users(self):
        repo_collaborators = []
        for collaborator in self.repo_collaborators:
            collaborator = collaborator.split('novobi')[0].replace('-', '')
            repo_collaborators.append(
                self.format_repo_collaborator(collaborator))

        sonar_users_list = {}
        for user in self.sonar_users_list:
            user_name = user.split('novobi')[0].replace('-', '')
            sonar_users_list[user_name] = user

        exist_user_in_group = self.get_users_in_group('dev')
        for user in sonar_users_list.keys():
            if user in repo_collaborators and sonar_users_list[user] not in exist_user_in_group:
                self.add_user_to_group(sonar_users_list[user], 'dev')
            elif sonar_users_list[user] in exist_user_in_group and user not in repo_collaborators:
                self.remove_user_in_group(sonar_users_list[user], 'dev')

    def get_users_in_group(self, user_type):
        url = self.host_url + '/api/user_groups/users'
        group_name = '?name=' + self.project_key + '-' + user_type
        api_url = url + group_name
        result = self.send_api_request(api_url, 'get', self.sonar_token).json()
        exist_users = []
        for user in result['users']:
            exist_users.append(user['login'])
        return exist_users

    def send_api_request(self, api_url, rtype, token):
        if rtype == 'post':
            result = requests.post(api_url, auth=HTTPBasicAuth(token, ''))
        elif rtype == 'get':
            result = requests.get(api_url, auth=HTTPBasicAuth(token, ''))
        return result

    def start(self, project_key, github_token, sonar_token):
        self.project_key = project_key
        self.github_token = github_token
        self.sonar_token = sonar_token

        # Get users
        self.get_repo_collaborators()
        self.get_sonar_users_list()

        # Add dev group
        self.create_user_group('dev')
        self.set_dev_group_users()

        # Add lead group
        self.create_user_group('lead')


if __name__ == '__main__':
    sonar = SonarNovobi()

    # Environment Variables
    project_key = os.getenv('REPOSITORY_NAME')
    github_token = os.getenv('GITHUB_TOKEN')
    sonar_token = os.getenv('SONAR_TOKEN')

    # Start Setup
    sonar.start(project_key, github_token, sonar_token)
