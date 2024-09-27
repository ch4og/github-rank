import requests
import os
import json
from flask import Flask, request, abort

app = Flask(__name__)


def expon_cdf(x: float) -> float:
    return 1 - 2 ** (-x)


def lognorm_cdf(x: float) -> float:
    return x / (1 + x)


medians = {
    "commits": 250,
    "prs": 50,
    "issues": 25,
    "reviews": 2,
    "stars": 50,
    "followers": 10,
}
weights = {
    "commits": 2,
    "prs": 3,
    "issues": 1,
    "reviews": 1,
    "stars": 4,
    "followers": 1,
}
stats = {
    "commits": 0,
    "prs": 0,
    "issues": 0,
    "reviews": 0,
    "stars": 0,
    "followers": 0,
    "rank": "",
}
levels = {
    1: "S",
    12.5: "A+",
    25: "A",
    37.5: "A-",
    50: "B+",
    62.5: "B",
    75: "B-",
    87.5: "C+",
    100: "C",
}


def get_rank(username):
    stats["rank"] = ""
    query = f"""
    {{
        user(login: "{username}") {{
            name
            login
            contributionsCollection {{
                totalCommitContributions
                totalPullRequestReviewContributions
            }}
            repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) {{
                totalCount
            }}
            pullRequests(first: 1) {{
                totalCount
            }}
            openIssues: issues(states: OPEN) {{
                totalCount
            }}
            closedIssues: issues(states: CLOSED) {{
                totalCount
            }}
            followers {{
                totalCount
            }}        
            repositories(first: 100, ownerAffiliations: OWNER, orderBy: {{direction: DESC, field: STARGAZERS}}) {{
                nodes {{
                    name
                stargazerCount
                }}
            }}
              
    }}
    }}
    """
    headers = {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        "https://api.github.com/graphql", json={"query": query}, headers=headers
    )

    if response.status_code != 200 or "errors" in response.text:
        abort(403)

    data = response.json()["data"]["user"]
    contributions = data["contributionsCollection"]
    stats["commits"] = contributions["totalCommitContributions"]
    stats["prs"] = data["pullRequests"]["totalCount"]
    stats["issues"] = (
        data["openIssues"]["totalCount"] + data["closedIssues"]["totalCount"]
    )
    stats["reviews"] = contributions["totalPullRequestReviewContributions"]
    stats["followers"] = data["followers"]["totalCount"]

    repos = response.json()["data"]["user"]["repositories"]["nodes"]

    stats["stars"] = 0
    for repo in repos:
        stats["stars"] += repo["stargazerCount"]

    total_weight = sum(weights.values())
    rank = (
        1
        - (
            weights["commits"] * expon_cdf(stats["commits"] / medians["commits"])
            + weights["prs"] * expon_cdf(stats["prs"] / medians["prs"])
            + weights["issues"] * expon_cdf(stats["issues"] / medians["issues"])
            + weights["reviews"] * expon_cdf(stats["reviews"] / medians["reviews"])
            + weights["stars"] * lognorm_cdf(stats["stars"] / medians["stars"])
            + weights["followers"]
            * lognorm_cdf(stats["followers"] / medians["followers"])
        )
        / total_weight
    )
    lower_values = [x for x in levels.keys() if x >= rank * 100]
    stats["rank"] = levels[min(lower_values)]

    return stats


@app.route("/")
def index():
    username = request.args.get("user")
    if username:
        stats = get_rank(username)
        return json.dumps(stats)
    else:
        abort(404)


if __name__ == "__main__":
    app.run(debug=True)
