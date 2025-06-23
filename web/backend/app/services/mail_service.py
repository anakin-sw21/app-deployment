from flask_mail import Mail, Message, Attachment

from web.backend.app.utils import enforce_types


@enforce_types
class MailService:
    def __init__(self, mail: Mail):
        self.__mail = mail

    def send_mail(self, subject: str = "",
             recipients: list[str | tuple[str, str]] | None = None,
             body: str | None = None,
             html: str | None = None,
             sender: str | tuple[str, str] | None = None,
             cc: list[str | tuple[str, str]] | None = None,
             bcc: list[str | tuple[str, str]] | None = None,
             attachments: list[Attachment] | None = None,
             reply_to: str | tuple[str, str] | None = None,
             date: float | None = None,
             charset: str | None = None,
             extra_headers: dict[str, str] | None = None,
             mail_options: list[str] | None = None,
             rcpt_options: list[str] | None = None):
        msg = Message(subject,
                      recipients,
                      body,
                      html,
                      sender,
                      cc,
                      bcc,
                      attachments,
                      reply_to,
                      date,
                      charset,
                      extra_headers,
                      mail_options,
                      rcpt_options
        )
        self.__mail.send(msg)