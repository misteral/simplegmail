import base64
import datetime
from email.mime.audio import MIMEAudio
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import html
import email.utils
import math
import mimetypes
import os
import re
import threading
from typing import List, Optional

from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials

from gmsa.authentication import AuthenticatedService
from gmsa.attachment import Attachment
from gmsa.label import Label
from gmsa.message import Message


class Gmail(AuthenticatedService):
    '''
    The Gmail class which serves as the entrypoint for the Gmail service API.
    '''
    def __init__(self, credentials: Optional[Credentials]=None, credentials_path: Optional[str]=None,
                 token_path: Optional[str]=None, save_token: bool=True, read_only: bool=False,
                 authentication_flow_host: str='localhost', authentication_flow_port: int=8080):
        '''
        Specify ``credentials`` to use in requests or ``credentials_path`` and ``token_path`` to get credentials from

        :param credentials:
                Credentials with token and refresh token.
                If specified, ``credentials_path``, ``token_path``, and ``save_token`` are ignored.
                If not specified, credentials are retrieved from "token.pickle" file (specified in ``token_path`` or
                default path) or with authentication flow using secret from "credentials.json" ("client_secret_*.json")
                (specified in ``credentials_path`` or default path)
        :param credentials_path:
                Path to "credentials.json" ("client_secret_*.json") file.
                Default: ~/.credentials/credentials.json or ~/.credentials/client_secret*.json
        :param token_path:
                Existing path to load the token from, or path to save the token after initial authentication flow.
                Default: "token.pickle" in the same directory as the credentials_path
        :param save_token:
                Whether to pickle token after authentication flow for future uses
        :param read_only:
                If require read only access. Default: False
        :param authentication_flow_host:
                Host to receive response during authentication flow
        :param authentication_flow_port:
                Port to receive response during authentication flow
        '''
        super().__init__(
            credentials=credentials,
            credentials_path=credentials_path,
            token_path=token_path,
            save_token=save_token,
            read_only=read_only,
            authentication_flow_host=authentication_flow_host,
            authentication_flow_port=authentication_flow_port,
        )


    def send_message(self, sender: str, to: str, subject: str='', msg_html: Optional[str]=None,
                     msg_plain: Optional[str]=None, cc: Optional[List[str]]=None,
                     bcc: Optional[List[str]]=None, attachments: Optional[List[str]]=None,
                     signature: bool=False, user_id: str='me') -> Message:
        '''
        Sends an email.

        Args:
            sender: The email address the message is being sent from.
            to: The email address the message is being sent to.
            subject: The subject line of the email.
            msg_html: The HTML message of the email.
            msg_plain: The plain text alternate message of the email. This is often displayed on
                slow or old browsers, or if the HTML message is not provided.
            cc: The list of email addresses to be cc'd.
            bcc: The list of email addresses to be bcc'd.
            attachments: The list of attachment file names.
            signature: Whether the account signature should be added to the message.
            user_id: The address of the sending account. 'me' for the default address associated
                with the account.
        Returns:
            The Message object representing the sent message.
        '''
        msg = self._create_message(
            sender, to, subject, msg_html, msg_plain, cc=cc, bcc=bcc,
            attachments=attachments, signature=signature, user_id=user_id
        )
        res = self.service.users().messages().send(userId='me', body=msg).execute()
        return self._build_message_from_ref(user_id, res, 'reference')


    def get_messages(self, user_id: str='me', labels: Optional[List[Label]]=None, query: str='',
                     attachments: str='reference', include_spam_trash: bool=False) -> List[Message]:
        '''
        Gets messages from your account.

        Args:
            user_id: the user's email address. Default 'me', the authenticated user.
            labels: label IDs messages must match.
            query: a Gmail query to match.
            attachments: Accepted values are 'ignore' which completely ignores all attachments,
                'reference' which includes attachment information but does not download the data,
                and 'download' which downloads the attachment data to store locally.
                Default 'reference'.
            include_spam_trash: whether to include messages from spam or trash.
        Returns:
            A list of message objects.
        '''
        if labels is None:
            labels = []

        labels_ids = [lbl.id if isinstance(lbl, Label) else lbl for lbl in labels]

        response = self.service.users().messages().list(
            userId=user_id,
            q=query,
            labelIds=labels_ids,
            includeSpamTrash=include_spam_trash
        ).execute()

        message_refs = []
        if 'messages' in response:  # ensure request was successful
            message_refs.extend(response['messages'])

        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = self.service.users().messages().list(
                userId=user_id,
                q=query,
                labelIds=labels_ids,
                includeSpamTrash=include_spam_trash,
                pageToken=page_token
            ).execute()

            message_refs.extend(response['messages'])

        return self._get_messages_from_refs(user_id, message_refs, attachments)


    def list_labels(self, user_id: str='me') -> List[Label]:
        '''
        Retrieves all labels for the specified user.

        These Label objects are to be used with other functions like
        modify_labels().

        Args:
            user_id: The user's email address. By default, the authenticated
                user.
        Returns:
            The list of Label objects.
        '''
        res = self.service.users().labels().list(userId=user_id).execute()

        labels = [Label(name=x['name'], id=x['id']) for x in res['labels']]
        return labels

    def create_label(self, name: str, user_id: str='me') -> Label:
        '''
        Creates a new label.

        Args:
            name: The display name of the new label.
            user_id: The user's email address. By default, the authenticated user.
        Returns:
            The created Label object.
        '''
        res = self.service.users().labels().create(userId=user_id, body={'name': name}).execute()
        return Label(res['name'], res['id'])

    def delete_label(self, label_: Label, user_id: str = 'me'):
        '''
        Deletes a label.

        Args:
            label: The label to delete.
            user_id: The user's email address. By default, the authenticated user.
        '''
        self.service.users().labels().delete(userId=user_id, id=label_.id).execute()


    def _get_messages_from_refs(self, user_id: str, message_refs: List[dict],
                                attachments: str='reference', parallel: bool=True) -> List[Message]:
        '''
        Retrieves the actual messages from a list of references.

        Args:
            user_id: The account the messages belong to.
            message_refs: A list of message references with keys id, threadId.
            attachments: Accepted values are 'ignore' which completely ignores all attachments,
                'reference' which includes attachment information but does not download the data,
                and 'download' which downloads the attachment data to store locally.
                Default 'reference'.
            parallel: Whether to retrieve messages in parallel. Default true. Currently
                parallelization is always on, since there is no reason to do otherwise.
        Returns:
            A list of Message objects.
        '''
        if not message_refs:
            return []

        if not parallel:
            return [self._build_message_from_ref(user_id, ref, attachments) for ref in message_refs]

        max_num_threads = 24  # empirically chosen, prevents throttling
        target_msgs_per_thread = 20  # empirically chosen
        num_threads = min(
            math.ceil(len(message_refs) / target_msgs_per_thread),
            max_num_threads
        )
        batch_size = math.ceil(len(message_refs) / num_threads)
        message_lists = [[] for _ in range(num_threads)]

        def thread_download_batch(thread_num):
            gmail = Gmail(credentials=self.credentials)

            start = thread_num * batch_size
            end = min(len(message_refs), (thread_num + 1) * batch_size)
            message_lists[thread_num] = [
                self._build_message_from_ref(user_id, message_refs[i], attachments)
                for i in range(start, end)
            ]

            gmail.service.close()

        threads = [
            threading.Thread(target=thread_download_batch, args=(i,))
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        return sum(message_lists, [])

    def _build_message_from_ref(self, user_id: str, message_ref: dict, attachments: str='reference') -> Message:
        '''
        Creates a Message object from a reference.

        Args:
            user_id: The username of the account the message belongs to.
            message_ref: The message reference object returned from the Gmail API.
            attachments: Accepted values are 'ignore' which completely ignores all attachments,
                'reference' which includes attachment information but does not download the data,
                and 'download' which downloads the attachment data to store locally.
                Default 'reference'.
        Returns:
            The Message object.
        '''
        # Get message JSON
        message = self.service.users().messages().get(userId=user_id, id=message_ref['id']).execute()

        msg_id = message['id']
        thread_id = message['threadId']
        label_ids = []
        if 'labelIds' in message:
            user_labels = {x.id: x for x in self.list_labels(user_id=user_id)}
            label_ids = [user_labels[x] for x in message['labelIds']]
        snippet = html.unescape(message['snippet'])

        payload = message['payload']
        headers = payload['headers']

        # Get header fields (date, from, to, subject)
        date = ''
        sender = ''
        recipient = ''
        subject = ''
        msg_hdrs = {}
        cc = []
        bcc = []
        for hdr in headers:
            if hdr['name'].lower() == 'date':
                try:
                    date = str(datetime.datetime.strptime(
                        hdr['value'], '%d %b %Y %H:%M:%S %z'
                    ).astimezone())
                except ValueError:
                    date = hdr['value']
            elif hdr['name'].lower() == 'from':
                sender = hdr['value']
            elif hdr['name'].lower() == 'to':
                recipient = hdr['value']
            elif hdr['name'].lower() == 'subject':
                subject = hdr['value']
            elif hdr['name'].lower() == 'cc':
                cc = hdr['value'].split(', ')
            elif hdr['name'].lower() == 'bcc':
                bcc = hdr['value'].split(', ')

            msg_hdrs[hdr['name']] = hdr['value']

        parts = self._evaluate_message_payload(payload, user_id, message_ref['id'], attachments)

        plain_msg=None
        html_msg=None
        attms = []
        for part in parts:
            if part['part_type'] == 'plain':
                if plain_msg is None:
                    plain_msg = part['body']
                else:
                    plain_msg += '\n' + part['body']
            elif part['part_type'] == 'html':
                if html_msg is None:
                    html_msg = part['body']
                else:
                    html_msg += '<br/>' + part['body']
            elif part['part_type'] == 'attachment':
                attm = Attachment(self.service, user_id, msg_id,
                                  part['attachment_id'], part['filename'],
                                  part['filetype'], part['data'])
                attms.append(attm)

        return Message(
            self.service, self.credentials, user_id, msg_id, thread_id, recipient, sender, subject,
            date, snippet, plain_msg, html_msg, label_ids, attms, msg_hdrs, cc, bcc
        )

    def _evaluate_message_payload(self, payload: dict, user_id: str, msg_id: str,
                                  attachments: str='reference') -> List[dict]:
        '''
        Recursively evaluates a message payload.

        Args:
            payload: The message payload object (response from Gmail API).
            user_id: The current account address (default 'me').
            msg_id: The id of the message.
            attachments: Accepted values are 'ignore' which completely ignores all attachments,
                'reference' which includes attachment information but does not download the data,
                and 'download' which downloads the attachment data to store locally.
                Default 'reference'.
        Returns:
            A list of message parts.
        '''
        if 'attachmentId' in payload['body']:  # if it's an attachment
            if attachments == 'ignore':
                return []

            att_id = payload['body']['attachmentId']
            filename = payload['filename']
            if not filename:
                filename = 'unknown'

            obj = {
                'part_type': 'attachment',
                'filetype': payload['mimeType'],
                'filename': filename,
                'attachment_id': att_id,
                'data': None
            }

            if attachments == 'reference':
                return [obj]

            else:  # attachments == 'download'
                if 'data' in payload['body']:
                    data = payload['body']['data']
                else:
                    res = self.service.users().messages().attachments().get(
                        userId=user_id, messageId=msg_id, id=att_id
                    ).execute()
                    data = res['data']

                file_data = base64.urlsafe_b64decode(data)
                obj['data'] = file_data
                return [obj]

        elif payload['mimeType'] == 'text/html':
            data = payload['body']['data']
            data = base64.urlsafe_b64decode(data)
            body = BeautifulSoup(data, 'lxml', from_encoding='utf-8').body
            return [{ 'part_type': 'html', 'body': str(body) }]

        elif payload['mimeType'] == 'text/plain':
            data = payload['body']['data']
            data = base64.urlsafe_b64decode(data)
            body = data.decode('UTF-8')
            return [{ 'part_type': 'plain', 'body': body }]

        elif payload['mimeType'].startswith('multipart'):
            ret = []
            if 'parts' in payload:
                for part in payload['parts']:
                    ret.extend(self._evaluate_message_payload(part, user_id, msg_id, attachments))
            return ret

        return []

    def _create_message(
        self,
        sender: str,
        to: str,
        subject: str = '',
        msg_html: str = None,
        msg_plain: str = None,
        cc: List[str] = None,
        bcc: List[str] = None,
        attachments: List[str] = None,
        signature: bool = False,
        user_id: str = 'me',
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None
    ) -> dict:
        """
        Creates the raw email message to be sent.

        Args:
            sender: The email address the message is being sent from.
            to: The email address the message is being sent to.
            subject: The subject line of the email.
            msg_html: The HTML message of the email.
            msg_plain: The plain text alternate message of the email (for slow
                or old browsers).
            cc: The list of email addresses to be Cc'd.
            bcc: The list of email addresses to be Bcc'd
            attachments: A list of attachment file paths.
            signature: Whether the account signature should be added to the
                message. Will add the signature to your HTML message only, or a
                create a HTML message if none exists.
            thread_id: The thread ID of the email being replied to.
            in_reply_to: The message ID of the email being replied to.
            references: The references header of the email being replied to.

        Returns:
            The message dict.

        """

        msg = MIMEMultipart('mixed' if attachments else 'alternative')
        msg['To'] = email.utils.formataddr(('Recipient', to.encode('ascii', 'ignore')), charset='utf-8')
        msg['From'] = email.utils.formataddr(('Sender', sender), charset='utf-8')
        msg['Subject'] = subject

        if cc:
            msg['Cc'] = ', '.join([email.utils.formataddr(('Recipient', addr), charset='utf-8') for addr in cc])

        if bcc:
            msg['Bcc'] = ', '.join([email.utils.formataddr(('Recipient', addr), charset='utf-8') for addr in bcc])
        if thread_id:
            msg['threadId'] = thread_id
            msg['Thread-Id'] = thread_id

        if in_reply_to:
            msg['In-Reply-To'] = in_reply_to

        if references:
            msg['References'] = references

        if signature:
            m = re.match(r'.+\s<(?P<addr>.+@.+\..+)>', sender)
            address = m.group('addr') if m else sender
            account_sig = self._get_alias_info(address, user_id)['signature']

            if msg_html is None:
                msg_html = ''

            msg_html += "<br /><br />" + account_sig

        # Create the alternative part for plain and HTML text
        alternative_part = MIMEMultipart('alternative')

        if msg_plain:
            alternative_part.attach(MIMEText(msg_plain, 'plain', 'utf-8'))

        if msg_html:
            alternative_part.attach(MIMEText(msg_html, 'html', 'utf-8'))

        if attachments:
            msg.attach(alternative_part)
            self._ready_message_with_attachments(msg, attachments)
        else:
            msg.attach(alternative_part)

        result = {}
        result['raw'] = base64.urlsafe_b64encode(msg.as_string().encode('utf-8')).decode('utf-8')
        if thread_id:
            result['threadId'] = thread_id

        return result

    def _ready_message_with_attachments(self, msg: MIMEMultipart, attachments: List[str]):
        '''
        Converts attachment filepaths to MIME objects and adds them to msg.

        Args:
            msg: The message to add attachments to.
            attachments: A list of attachment file paths.
        '''
        for filepath in attachments:
            content_type, encoding = mimetypes.guess_type(filepath)

            if content_type is None or encoding is not None:
                content_type = 'application/octet-stream'

            main_type, sub_type = content_type.split('/', 1)
            with open(filepath, 'rb') as file:
                raw_data = file.read()

                attm: MIMEBase
                if main_type == 'text':
                    attm = MIMEText(raw_data.decode('UTF-8'), _subtype=sub_type)
                elif main_type == 'image':
                    attm = MIMEImage(raw_data, _subtype=sub_type)
                elif main_type == 'audio':
                    attm = MIMEAudio(raw_data, _subtype=sub_type)
                elif main_type == 'application':
                    attm = MIMEApplication(raw_data, _subtype=sub_type)
                else:
                    attm = MIMEBase(main_type, sub_type)
                    attm.set_payload(raw_data)

            fname = os.path.basename(filepath)
            attm.add_header('Content-Disposition', 'attachment', filename=fname)
            msg.attach(attm)

    def _get_alias_info(self, send_as_email: str, user_id: str='me') -> dict:
        '''
        Returns the alias info of an email address on the authenticated
        account.

        Response data is of the following form:
            {
                "sendAsEmail": string,
                "displayName": string,
                "replyToAddress": string,
                "signature": string,
                "isPrimary": boolean,
                "isDefault": boolean,
                "treatAsAlias": boolean,
                "smtpMsa": {
                    "host": string,
                    "port": integer,
                    "username": string,
                    "password": string,
                    "securityMode": string
                },
                "verificationStatus": string
            }
        Args:
            send_as_email: The alias account information is requested for
                (could be the primary account).
            user_id: The user ID of the authenticated user the account the
                alias is for (default "me").
        Returns:
            The dict of alias info associated with the account.
        '''
        req =  self.service.users().settings().sendAs().get(
            sendAsEmail=send_as_email, userId=user_id
        )
        res = req.execute()
        return res

    def get_thread_messages(
        self,
        thread_id: str,
        user_id: str = 'me',
        attachments: str = 'reference'
    ) -> List[Message]:
        """
        Gets all messages with the specified thread_id.

        Args:
            thread_id: The thread ID to match.
            user_id: The user's email address. By default, the authenticated user.
            attachments: Accepted values are 'ignore' which completely ignores all attachments,
                         'reference' which includes attachment information but does not download the data,
                         and 'download' which downloads the attachment data to store locally. Default 'reference'.

        Returns:
            A list of Message objects.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the HTTP request.
        """

        response = self.service.users().threads().get(
            userId=user_id,
            id=thread_id
        ).execute()

        message_refs = response.get('messages', [])

        return self._get_messages_from_refs(user_id, message_refs, attachments)

    def reply_message(
        self,
        message: Message,
        reply_text: Optional[str] = None,
        msg_html: Optional[str] = None,
        msg_plain: Optional[str] = None,
        signature: bool = False,
        attachments: Optional[List[str]] = None,
        user_id: str = 'me'
    ) -> Message:
        """
        Replies to an email.

        Args:
            message: The Message object representing the email being replied to.
            reply_text: The text to include in the reply.
            msg_html: The HTML message of the reply.
            msg_plain: The plain text alternate message of the reply.
            attachments: The list of attachment file names.
            signature: Whether the account signature should be added to the reply.

        Returns:
            The Message object representing the sent message.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        original_msg_html = message.html or ""
        original_msg_plain = message.plain or ""

        if not msg_html:
            msg_html = f"{reply_text} <br><br>On {message.date}, {message.sender} wrote:<br>{original_msg_html}"
        if not msg_plain:
            msg_plain = f"{reply_text} \n\nOn {message.date}, {message.sender} wrote:\n{original_msg_plain}"
        references = message.id
        msg = self._create_message(
            message.recipient, message.sender, f"Re: {message.subject}", msg_html, msg_plain,
            signature=signature, user_id=user_id, attachments=attachments, thread_id=message.thread_id,
            in_reply_to=message.id, references=references
        )

        try:
            req = self.service.users().messages().send(userId='me', body=msg)
            res = req.execute()
        except Exception as e:
            print(f"Error: {e}")
            print(f"Message: {message}")
            raise

        return self._build_message_from_ref(user_id, res, 'reference')


