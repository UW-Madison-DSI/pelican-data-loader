import json
import logging
import os
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Person(BaseModel):
    first_name: str
    last_name: str
    email: str
    department_unit: str
    title: str
    person_api_id: str
    netid: str
    hrs_employee_id: str
    cost_center_id: str = ""
    cost_center_name: str = ""
    employee_category: str
    office_address: str = ""
    office_phone: str = ""
    years_employed: int
    retired: bool


def get_oauth_token() -> str:
    """Obtain OAuth token from Wisc API."""

    oauth_url = os.getenv("WISC_OAUTH_URL")
    if not oauth_url:
        raise ValueError("WISC_OAUTH_URL environment variable is not set.")

    response = httpx.post(
        url=oauth_url,
        data={
            "client_id": os.getenv("WISC_CLIENT_ID"),
            "client_secret": os.getenv("WISC_CLIENT_SECRET"),
            "grant_type": "client_credentials",
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def download_faculties() -> None:
    """Download all faculty data from the Wisc API and save to disk."""
    token = get_oauth_token()
    url = "https://api.wisc.edu/people/?filter[jobs.employeeCategory]=Faculty"
    faculties = []

    while url:
        response = httpx.get(url, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        data = response.json()
        faculties.extend(data["data"])
        logging.info(f"Downloaded faculty {len(faculties)}")

        url = data["links"].get("next")

    os.makedirs("tmp", exist_ok=True)
    with open("tmp/uw_faculties_person_api.json", "w") as f:
        json.dump(faculties, f, indent=4)


def get_best_person_id(data: dict) -> str:
    """Select the best person from a list based on data completeness."""
    if len(data["data"]) == 1:
        return data["data"][0]["id"]

    def calculate_score(person_data: dict) -> float:
        score = 0
        attrs = person_data.get("attributes", {})
        # +3 for email
        if attrs.get("emailAddress"):
            score += 3
        # +1 for office address
        if attrs.get("officeAddress"):
            score += 1
        # +1 per associated job id
        jobs = person_data.get("relationships", {}).get("jobs", {}).get("data", [])
        score += len(jobs)
        return score

    scores = [calculate_score(person) for person in data["data"]]
    best_person_index = scores.index(max(scores))
    return data["data"][best_person_index]["id"]


def filter_best_person(data: dict) -> dict:
    """Filter out unnecessary data and only keep the best person."""
    best_id = get_best_person_id(data)
    output = {
        "data": [x for x in data["data"] if x["id"] == best_id],
        "included": [
            x
            for x in data.get("included", [])
            if x.get("relationships", {}).get("person", {}).get("data", {}).get("id") == best_id
        ],
    }
    return output


class PersonParser:
    @staticmethod
    def camel_to_snake(text: str) -> str:
        return "".join(["_" + c.lower() if c.isupper() else c for c in text]).lstrip("_")

    @staticmethod
    def unpack_raw(data: dict) -> dict:
        return data["data"][0] if isinstance(data["data"], list) else data["data"]

    def _get_person_api_id(self, data: dict) -> str:
        return self.unpack_raw(data)["id"]

    def _get_first_name(self, data: dict) -> str:
        return self.unpack_raw(data)["attributes"]["firstName"]

    def _get_last_name(self, data: dict) -> str:
        return self.unpack_raw(data)["attributes"]["lastName"]

    def _get_email(self, data: dict) -> str:
        return self.unpack_raw(data)["attributes"]["emailAddress"]

    def _get_office_address(self, data: dict) -> str:
        return self.unpack_raw(data)["attributes"].get("officeAddress", "")

    def _get_office_phone(self, data: dict) -> str:
        return self.unpack_raw(data)["attributes"].get("officePhoneNumber", "")

    @staticmethod
    def _get_includes_attr(
        data: dict,
        type: str,
        current_only: bool = True,
        institution: str = "UW-Madison",
        id: str | None = None,
    ) -> list[dict]:
        includes = data.get("included", [])
        attributes = [
            include["attributes"]
            for include in includes
            if include.get("type") == type and include["attributes"].get("institution") == institution
        ]
        if current_only:
            attributes = [attr for attr in attributes if attr.get("current")]
        if id:
            attributes = [
                attr
                for attr in attributes
                if attr.get("relationships", {}).get("person", {}).get("data", {}).get("id") == id
            ]
        return attributes

    def _get_netid(self, data: dict) -> str | None:
        identifiers = self._get_includes_attr(data, type="identifiers")
        for x in identifiers:
            if x.get("name") == "netId":
                return x.get("value")
        return None

    def _get_hrs_employee_id(self, data: dict) -> str | None:
        identifiers = self._get_includes_attr(data, type="identifiers")
        for x in identifiers:
            if x.get("source") == "HRS" and x.get("name") == "emplId":
                return x.get("value")
        return None

    def _get_years_employed(self, data: dict) -> int:
        jobs = self._get_includes_attr(data, type="jobs", current_only=False)
        if not jobs:
            return 0
        earliest_start_date = min([job["beginDate"] for job in jobs])
        d = datetime.now() - datetime.strptime(earliest_start_date, "%Y-%m-%d")
        return d.days // 365

    def _get_active_job_details(self, data: dict) -> dict:
        jobs = self._get_includes_attr(data, type="jobs", current_only=True)
        if not jobs:
            logging.warning("Not currently employed.")
            raise ValueError("Not currently employed.")

        workday_primary_job = [job for job in jobs if job.get("primary") and job.get("source") == "Workday"]
        if not workday_primary_job:
            raise ValueError("No primary Workday job found.")

        if len(workday_primary_job) > 1:
            workday_primary_job = sorted(
                workday_primary_job,
                key=lambda x: float(x.get("fullTimeEquivalent", 0)),
                reverse=True,
            )
            logging.warning(f"Multiple primary Workday jobs found, selected: {workday_primary_job[0]}")
            workday_primary_job = [workday_primary_job[0]]

        primary_job = workday_primary_job[0].copy()
        primary_job["retired"] = False

        hrs_primary_job = [
            job
            for job in jobs
            if job.get("primary")
            and job.get("source") == "HRS"
            and job.get("employeeCategory") == primary_job.get("employeeCategory")
            and job.get("title") == primary_job.get("title")
        ]
        if hrs_primary_job:
            hrs_primary_job = sorted(
                hrs_primary_job,
                key=lambda x: float(x.get("fullTimeEquivalent", 0)),
                reverse=True,
            )
            primary_job["departmentUnit"] = hrs_primary_job[0].get("departmentUnit", "")
        else:
            primary_job["departmentUnit"] = ""
        return primary_job

    def _get_latest_inactive_job(self, data: dict) -> dict[str, Any]:
        jobs = self._get_includes_attr(data, type="jobs", current_only=False)
        if not jobs:
            raise ValueError("No job found.")
        latest_job = sorted(jobs, key=lambda x: x["beginDate"])[-1]
        latest_job["retired"] = True
        return latest_job

    def _parse(self, data: dict) -> dict:
        if len(data["data"]) > 1:
            data = filter_best_person(data)
        try:
            job_details = self._get_active_job_details(data)
        except ValueError:
            job_details = self._get_latest_inactive_job(data)
        other_details = {
            "person_api_id": self._get_person_api_id(data),
            "netid": self._get_netid(data),
            "hrs_employee_id": self._get_hrs_employee_id(data),
            "first_name": self._get_first_name(data),
            "last_name": self._get_last_name(data),
            "email": self._get_email(data),
            "office_address": self._get_office_address(data),
            "office_phone": self._get_office_phone(data),
            "years_employed": self._get_years_employed(data),
        }
        parsed = {**job_details, **other_details}
        return {self.camel_to_snake(k): v for k, v in parsed.items() if v is not None}

    def parse(self, data: dict) -> Person:
        parsed_data = self._parse(data)
        return Person(**parsed_data)


def get_raw_person(first_name: str, last_name: str) -> dict:
    """Fetch raw person data from the Wisc API by name."""
    token = get_oauth_token()
    base_url = "https://api.wisc.edu/people/"
    params = {
        "include": "identifiers,jobs",
        "fields[identifiers]": "name,source,value,current,institution",
        "fields[jobs]": "source,primary,current,fullTimeEquivalent,employeeCategory,institution,departmentUnit,costCenterName,costCenterId,title,beginDate,endDate",
        "filter[firstName]": first_name,
        "filter[lastName]": last_name,
    }
    url = base_url + "?" + urlencode(params)
    response = httpx.get(url, headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    logging.debug(response.json())
    return response.json()


def get_person(first_name: str, last_name: str) -> Person:
    """Get a parsed Person object by first and last name."""
    raw = get_raw_person(first_name, last_name)
    if not raw.get("data"):
        raise ValueError(f"No person found with name {first_name} {last_name}")
    if isinstance(raw["data"], list) and len(raw["data"]) > 1:
        logging.warning(
            f"Multiple people found with name {first_name} {last_name}, selecting the best one. ids: {[x.get('id') for x in raw['data']]}"
        )
    return PersonParser().parse(raw)


def get_person_by_id(id: str) -> Person:
    """Get a parsed Person object by API ID."""
    token = get_oauth_token()
    base_url = f"https://api.wisc.edu/people/{id}"
    params = {
        "include": "identifiers,jobs",
        "fields[identifiers]": "source,current,institution,name,value",
        "fields[jobs]": "source,primary,current,fullTimeEquivalent,employeeCategory,institution,departmentUnit,costCenterName,costCenterId,title,beginDate,endDate",
    }
    url = base_url + "?" + urlencode(params)
    response = httpx.get(url, headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    logging.debug(response.json())
    if not response.json().get("data"):
        raise ValueError(f"No person found with id {id}")
    return PersonParser().parse(response.json())
