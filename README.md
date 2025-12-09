# CodeConnect

## Development Setup
You will need [Node.js](https://nodejs.org/) installed if you want to edit [Tailwindcss](https://tailwindcss.com/) (a css framework).
```sh
npm install
```
```sh
npm run tw
```
Choose either [Python](https://www.python.org/) or [Docker](https://www.docker.com/). (They will work the about same I just prefer Docker). 
### With Python
```sh
pip install -r requirements.txt
```
```sh
flask run
```
http://localhost:5000

### With Docker
```sh
docker compose up -w
```
http://localhost

## TODO
- [ ]  Convert to sendgrid support
- [ ]  Add email verification
- [ ]  Add emailing for every comment post
- [ ]  Add emailing for custom messages on projects
- [ ]  Add emailing for when job is applied. A confirmation email for applier. And notifaction email for the business
- [ ]  There's probably a bunch of permission issues such as having access to things users shouldn't
- [ ]  There's probably some other security flaws
- [ ]  When cookie is invaild server crashes. It should delete the cookie in browser.
- [ ]  You can definitely better abstract things out (ex. Uploads, Emails, Project file structure).
- [ ]  Add support for alert messages to notify user what happened (ex. Success and Error)
- [ ]  Replace POST with also PUT, PATCH, DELETE where it applies. (Functional no different but is more inline with modern standards)
- [ ]  Remove the unnecessary page refreshes to be more inline with modern web practices
- [ ]  You should probably use ```{{ url_for('') }}``` in your HTML. (Shouldn't make a difference but is more idiomatic)
