import json
import requests

from alerts import Alerter, DateTimeEncoder
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

        self.url = 'https://%s.ryver.com/api/1/odata.svc' % (self.ryver_organization)

        self.ryver_forum_id = self.rule.get('ryver_forum_id')
        self.ryver_team_id = self.rule.get('ryver_team_id')
        self.ryver_topic_id = self.rule.get('ryver_topic_id')

        if len(filter(lambda x: x, [self.ryver_forum_id, self.ryver_team_id, self.ryver_topic_id])) != 1:
            raise EAException(
                'You need to specify one and only one of following options: '
                'ryver_forum_id, ryver_team_id, ryver_topic_id'
            )

    def alert(self, matches):
        body = self.create_alert_body(matches)

        sender = {}
        if self.rule.get('ryver_avatar'):
            sender['avatar'] = self.rule.get('ryver_avatar')

        if self.rule.get('ryver_display_name'):
            sender['displayName'] = self.rule.get('ryver_display_name')

        if self.ryver_topic_id:
            url_path = "postComments?$format=json".format(self.url)
            json_content = {
                'comment': body,
                'post': {"id": self.ryver_topic_id},
            }

        elif self.ryver_team_id:
            url_path = "workrooms({})/Chat.PostMessage()".format(self.ryver_team_id)
            json_content = {"body": body, "createSource": sender}

        else:
            url_path = "forums({})/Chat.PostMessage()".format(self.ryver_forum_id)
            json_content = {"body": body, "createSource": sender}

        try:
            response = requests.post(
                "{}/{}".format(self.url, url_path),
                headers={
                    'content-type': 'application/json',
                    'Authorization': 'Basic {}'.format(self.ryver_auth_basic),
                },
                json=json_content
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise EAException("Error posting to Ryver: %s" % e)

        elastalert_logger.info("Alert sent to Ryver topic %s" % self.ryver_topic_id)

    def get_info(self):
        return {
            'type': 'ryver',
            'ryver_organization': self.ryver_organization,
            'ryver_forum_id': self.ryver_forum_id,
            'ryver_team_id': self.ryver_team_id,
            'ryver_topic_id': self.ryver_topic_id,
        }
