# pdf-print-service
WebService for making PDF file from HTML template or external URL, using wkhtmltopdf

## Usage

To make PDF file, you have to send a POST request to `/pdf` with following parameters included in JSON into 
request's body:

- `url`: url of the page to convert to PDF
- `cookies`: list of tuples (name, value) defining cookies to send. It is used to provide authentication token.
 
The request has to be authenticated by BASIC-AUTH
