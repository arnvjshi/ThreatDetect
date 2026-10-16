const nodemailer = require('nodemailer');

function createTransporter() {
  const smtpHost = process.env.SMTP_HOST || process.env.EMAIL_HOST || 'smtp.gmail.com';
  const smtpPort = parseInt(process.env.SMTP_PORT || process.env.EMAIL_PORT || 587);
  const secure = smtpPort === 465;

  const transporter = nodemailer.createTransport({
    host: smtpHost,
    port: smtpPort,
    secure: secure,
    auth: {
      user: (process.env.EMAIL_USER || '').trim(),
      pass: (process.env.EMAIL_PASSWORD || '').replace(/\s+/g, ''),
    },
  });

  return transporter;
}

module.exports = { createTransporter };
