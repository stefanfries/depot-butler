# Business Objective

## Initial situation

I am the subscriber of the Megatrend-Folger publication which is issued on a weekly basis. Each edition contains a table of a so-called "Musterdepot" listing the details of up to approx. 25 Call Warrants:

- Unternehmen (underlying)
- WKN
- Stück / quantity
- Kaufdatum / buying date
- Kaufkurs / buying price
- Akt. Kurs
- Kurswert
- Performance. (in %)
- Anteil

Below the table the total value of all items as well as the Cash value in the "Musterdepot" for the time of publication are given.
Currently I have the weekly publications of the last 15 years as pdf files.

## Business intention

From the weekly publications (the historical ones as well as the new ones issued every week) I want to extract some of the details of the table (WKN, underliying, Quantity, Kaufdatum, Kaufkurs) to track the performance of the depot over time. Therefore, I want to build the entire history of the depot in MongoDB.

If the composition of the depot has changed compared to last weeks edtion due to any BUY oder SELL transactions, the depot history must be updated and a new depot entry must be added with a "valid_from" date according to the date of publication. If there is no change in the depot, only the "last_updated" value of the last depot entry will be updated.

To also get the depot values between publishing dates I want to extract the WKNs of the most recent depot. A separate job (running every weekday evening after market close) should fetch the prices (for a time period and interval provided) for every WKN in the list and save the data to the MongoDB.
By these means I am the able to track the performance of the entire depot as well as the performace of every single WKN and use these data for further evaluation and recommendations.

## Questions / advise needed

1. How to structure the code for the various jobs:

- extract the Musterdepot table from the publication pdf and update MongoDB each time a new Megarend Folger publication has been processed
- extract all WKNs of the most recent depot for further processing by intrady price data fetcher
- fetch intraday price data from the web and store them to MongoDB

2. How to structure the workflow(s)?

- create one big workflow covering all steps needed?
- split the workflow into seperate logical parts to gain flexibility in composing individual workflows. These parts could be:

    - download (from the boersenmedien website)
    - distribute (via email and/or OneDrive upload)
    - extract Musterdepot table from pdf and update depot history
    - any post processing activites (like BUY/SELL recommendations based on specific evaluation)

3. How to structure the Git respositories

- backend and frontend components
- single repo vs multi repo
- and perhaps many more questions whch will come up over time

Can you assist on these questions?

4. How / where to store the publications

- currently publications are stored only temporarily on a file services in Azure and they are deleted (cleanup) after distribution
- would is probably better to store them permanenttly on Azure, e.g. for 1 or 10 years (a single edition takes aproc 800 kB).
- what would this cost in Azure? Are there cost effictive options like using archive store or a hierarchical storage system?
