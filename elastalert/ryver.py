import requests

from alerts import Alerter
from util import elastalert_logger, EAException


class RyverAlerter(Alerter):
    """ Post a new message in a Ryver topica, forum or team chat.

    Required fields:
      * ryver_auth_basic:
         Currently Ryver supports only basic auth (cf: https://api.ryver.com/ryvrest_api_examples.html#authentication).
         This params represent the base64 encoded user:password string.

      * ryver_organization: Your Ryver organization name.

    And one of:
      * ryver_forum_id: The ID of the public forum in which you want to send the alert to.
      * ryver_team_id: The ID of the private forum in which you want to send the alert to.
      * ryver_topic_id: The ID of the topic in which you want to send the alert to.

    Optional fields:
      * ryver_display_name: Override the username of the sender of the message in Ryver (for public/team forum only).
      * ryver_avatar: URL pointing to an avatar for the sender of the message in Ryver (for public/team forum only).
    """
    required_options = frozenset(['ryver_auth_basic', 'ryver_organization'])

    def __init__(self, rule):
        super(RyverAlerter, self).__init__(rule)
        self.ryver_auth_basic = self.rule['ryver_auth_basic']
        self.ryver_organization = self.rule['ryver_organization']

        sender = {}
        if self.rule.get('ryver_avatar'):
            sender['avatar'] = self.rule.get('ryver_avatar')

        if self.rule.get('ryver_display_name'):
            sender['displayName'] = self.rule.get('ryver_display_name')

        ryver_id_names = ['ryver_forum_id', 'ryver_team_id', 'ryver_topic_id']
        url_path = None
        for name in ryver_id_names:
            ryver_id = self.rule.get(name)
            if ryver_id is None:
                continue

            elif url_path is not None:
                # Check that only one of ryver_names is configured
                url_path = None
                break

            if name == 'ryver_topic_id':
                url_path = "postComments?$format=json"
                self.content_factory = lambda body: {'comment': body, 'post': {'id': ryver_id}}
                self.log_message = "Alert sent to Ryver forum: {}".format(ryver_id)

            elif name == 'ryver_team_id':
                url_path = "workrooms({})/Chat.PostMessage()".format(ryver_id)
                self.content_factory = lambda body: {"body": body, "createSource": sender}
                self.log_message = "Alert sent to Ryver team: {}".format(ryver_id)

            elif name == 'ryver_forum_id':
                url_path = "forums({})/Chat.PostMessage()".format(ryver_id)
                self.content_factory = lambda body: {"body": body, "createSource": sender}
                self.log_message = "Alert sent to Ryver forum: {}".format(ryver_id)

        if url_path is None:
            raise EAException(
                'You need to specify one and only one of following options: '
                'ryver_forum_id, ryver_team_id, ryver_topic_id'
            )

        self.url = "https://{}.ryver.com/api/1/odata.svc/{}".format(self.ryver_organization, url_path)
        self.headers = {
            'content-type': 'application/json',
            'Authorization': 'Basic {}'.format(self.ryver_auth_basic),
        }

    def alert(self, matches):
        body = self.create_alert_body(matches)
        json_content = self.content_factory(body)

        try:
            response = requests.post(self.url, headers=self.headers, json=json_content)
            response.raise_for_status()
        except requests.RequestException as e:
            raise EAException("Error posting to Ryver: {}".format(e))

        elastalert_logger.info(self.log_message)

    def get_info(self):
        return {
            'type': 'ryver',
            'url': self.url,
        }
