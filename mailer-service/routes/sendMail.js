const express = require('express');
const { createTransporter } = require('../config/transporter');

const router = express.Router();

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function markdownToHtml(markdown = '') {
  const safe = escapeHtml(markdown);
  const withBold = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  return withBold.replace(/\n/g, '<br />');
}

function buildTemplate({ email, summary, threat_level, video_url, thumbnail_src, timestamp }) {
  const summaryHtml = markdownToHtml(summary);
  const thumbnailBlock = thumbnail_src
    ? `
      <p style="margin: 16px 0 8px;"><strong>Scene Snapshot:</strong></p>
      <img src="${thumbnail_src}" alt="Event thumbnail" style="width: 100%; max-width: 560px; border-radius: 12px; border: 1px solid #e2e8f0;" />
    `
    : '';

  const videoBlock = video_url
    ? `<p><strong>Video Clip:</strong> <a href="${video_url}">${video_url}</a></p>`
    : '<p><strong>Video Clip:</strong> Not available</p>';

  return `
    <div style="font-family: Arial, sans-serif; color: #111827; line-height: 1.6;">
      <h2 style="margin: 0 0 16px; color: #0f172a;">Threat Detected</h2>
      <p><strong>Recipient:</strong> ${escapeHtml(email)}</p>
      <p><strong>Threat Level:</strong> ${escapeHtml(threat_level)}</p>
      <p><strong>Timestamp:</strong> ${escapeHtml(timestamp || new Date().toISOString())}</p>
      <p><strong>Summary:</strong><br />${summaryHtml}</p>
      ${thumbnailBlock}
      ${videoBlock}
    </div>
  `;
}

router.post('/send-alert', async (req, res) => {
  const { email, subject, summary, threat_level, video_url, thumbnail_url, thumbnail_base64, timestamp } = req.body || {};

  if (!email || !subject || !summary || !threat_level) {
    return res.status(400).json({ message: 'Missing required fields' });
  }

  try {
    const transporter = createTransporter();
    const attachments = [];
    let thumbnailSrc = thumbnail_url;
    if (thumbnail_base64) {
      attachments.push({
        filename: 'scene-thumbnail.jpg',
        content: thumbnail_base64,
        encoding: 'base64',
        cid: 'scene-thumbnail',
      });
      thumbnailSrc = 'cid:scene-thumbnail';
    }
    const message = {
      from: process.env.EMAIL_USER,
      to: email,
      subject,
      html: buildTemplate({ email, summary, threat_level, video_url, thumbnail_src: thumbnailSrc, timestamp }),
      attachments,
    };

    const info = await transporter.sendMail(message);
    return res.status(200).json({ message: 'Alert sent', messageId: info.messageId });
  } catch (error) {
    return res.status(500).json({ message: 'Failed to send alert', error: error.message });
  }
});

module.exports = router;
