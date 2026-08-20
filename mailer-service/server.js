require('dotenv').config();

const express = require('express');
const sendMailRouter = require('./routes/sendMail');

const app = express();
const port = Number(process.env.PORT || 5001);

app.use(express.json({ limit: '4mb' }));
app.use(sendMailRouter);

app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

app.listen(port, () => {
  console.log(`Mailer service listening on port ${port}`);
});
