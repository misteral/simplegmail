from typing import List, Optional, Union

from googleapiclient import discovery
from google.oauth2.credentials import Credentials

from gmsa import label
from gmsa.attachment import Attachment
from gmsa.label import Label


class Message:
    '''
    The Message class for emails in your Gmail mailbox. This class should not
    be manually constructed. Contains all information about the associated
    message, and can be used to modify the message's labels (e.g., marking as
    read/unread, archiving, moving to trash, starring, etc.).

    Args:
        service: the Gmail service object.
        user_id: the username of the account the message belongs to.
        msg_id: the message id.
        thread_id: the thread id.
        recipient: who the message was addressed to.
        sender: who the message was sent from.
        subject: the subject line of the message.
        date: the date the message was sent.
        snippet: the snippet line for the message.
        plain: the plaintext contents of the message. Default None.
        html: the HTML contents of the message. Default None.
        label_ids: the ids of labels associated with this message. Default [].
        attachments: a list of attachments for the message. Default [].
        headers: a dict of header values. Default {}
        cc: who the message was cc'd on the message.
        bcc: who the message was bcc'd on the message.
    '''
    def __init__(
        self,
        service: discovery.Resource,
        credentials: Credentials,
        user_id: str,
        msg_id: str,
        thread_id: str,
        recipient: str,
        sender: str,
        subject: str,
        date: str,
        snippet,
        plain: Optional[str]=None,
        html: Optional[str]=None,
        label_ids: Optional[List[str]]=None,
        attachments: Optional[List[Attachment]]=None,
        headers: Optional[dict]=None,
        cc: Optional[List[str]]=None,
        bcc: Optional[List[str]]=None
    ):
        self.service = service
        self.creds = credentials
        self.user_id = user_id
        self.id = msg_id
        self.thread_id = thread_id
        self.recipient = recipient
        self.sender = sender
        self.subject = subject
        self.date = date
        self.snippet = snippet
        self.plain = plain
        self.html = html
        self.label_ids = label_ids or []
        self.attachments = attachments or []
        self.headers = headers or {}
        self.cc = cc or []
        self.bcc = bcc or []

    def mark_as_read(self):
        'Marks this message as read (by removing the UNREAD label)'
        self.remove_label(label.UNREAD)

    def mark_as_unread(self):
        'Marks this message as unread (by adding the UNREAD label)'
        self.add_label(label.UNREAD)

    def mark_as_spam(self):
        'Marks this message as spam (by adding the SPAM label)'
        self.add_label(label.SPAM)

    def mark_as_not_spam(self):
        'Marks this message as not spam (by removing the SPAM label)'
        self.remove_label(label.SPAM)

    def mark_as_important(self):
        'Marks this message as important (by adding the IMPORTANT label)'
        self.add_label(label.IMPORTANT)

    def mark_as_not_important(self):
        'Marks this message as not important (by removing the IMPORTANT label)'
        self.remove_label(label.IMPORTANT)

    def star(self):
        'Stars this message (by adding the STARRED label)'
        self.add_label(label.STARRED)

    def unstar(self):
        'Unstars this message (by removing the STARRED label)'
        self.remove_label(label.STARRED)

    def move_to_inbox(self):
        'Moves an archived message to your inbox (by adding the INBOX label)'
        self.add_label(label.INBOX)

    def archive(self):
        'Archives the message (removes from inbox by removing the INBOX label)'
        self.remove_label(label.INBOX)

    def has_attachments(self) -> bool:
        'Returns whether this message has attachments'
        return len(self.attachments) > 0

    def trash(self):
        'Moves this message to the trash'
        res = self.service.users().messages().trash(userId=self.user_id, id=self.id).execute()

        assert label.TRASH in res['labelIds'], 'An error occurred in a call to `trash`.'

        self.label_ids = res['labelIds']

    def untrash(self):
        'Removes this message from the trash'
        res = self.service.users().messages().untrash(userId=self.user_id, id=self.id).execute()

        assert label.TRASH not in res['labelIds'], 'An error occurred in a call to `untrash`.'

        self.label_ids = res['labelIds']

    def move_from_inbox(self, to: Union[Label, str]):
        '''
        Moves a message from your inbox to another label "folder".

        Args:
            to: The label to move to.
        '''
        self.modify_labels(to, label.INBOX)

    def add_label(self, to_add: Union[Label, str]):
        '''
        Adds the given label to the message.

        Args:
            to_add: The label to add.
        '''
        self.add_labels([to_add])

    def add_labels(self, to_add: Union[List[Label], List[str]]):
        '''
        Adds the given labels to the message.

        Args:
            to_add: The list of labels to add.
        '''
        self.modify_labels(to_add, [])

    def remove_label(self, to_remove: Union[Label, str]):
        '''
        Removes the given label from the message.

        Args:
            to_remove: The label to remove.
        '''
        self.remove_labels([to_remove])

    def remove_labels(self, to_remove: Union[List[Label], List[str]]):
        '''
        Removes the given labels from the message.

        Args:
            to_remove: The list of labels to remove.
        '''
        self.modify_labels([], to_remove)

    def modify_labels(self, to_add: Union[Label, str, List[Label], List[str]],
                      to_remove: Union[Label, str, List[Label], List[str]]):
        '''
        Adds or removes the specified label.

        Args:
            to_add: The label or list of labels to add.
            to_remove: The label or list of labels to remove.
        '''
        if isinstance(to_add, (Label, str)):
            to_add = [to_add]

        if isinstance(to_remove, (Label, str)):
            to_remove = [to_remove]

        def create_update_labels() -> dict:
            'Creates an object for updating message label.'
            return {
                'addLabelIds': [
                    lbl.id if isinstance(lbl, Label) else lbl for lbl in to_add
                ],
                'removeLabelIds': [
                    lbl.id if isinstance(lbl, Label) else lbl for lbl in to_remove
                ]
            }

        res = self.service.users().messages().modify(
            userId=self.user_id, id=self.id, body=create_update_labels()
        ).execute()

        assert all((lbl in res['labelIds'] for lbl in to_add)) \
            and all((lbl not in res['labelIds'] for lbl in to_remove)), \
            'An error occurred while modifying message label.'

        self.label_ids = res['labelIds']
