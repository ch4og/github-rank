import github
import sys
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


def get_rank(username: str) -> str:
    g = github.Github()
    user = g.search_users(str(username) + " in:login")[0]

    query = f"author:{user.login} is:public"
    commits = g.search_commits(query)
    for commit in commits:
        if commit:
            stats["commits"] += 1
    medians["commits"] = 1000

    query = f"is:pr author:{user.login}"
    prs = g.search_issues(query)
    for pr in prs:
        stats["prs"] += 1

    query = f"is:issue author:{user.login}"
    issues = g.search_issues(query)
    for issue in issues:
        stats["issues"] += 1

    query = f"is:pr reviewed-by:{user.login}"
    reviews = g.search_issues(query)
    for review in reviews:
        stats["reviews"] += 1

    query = f"is:repo owner:{user.login}"
    repos = g.search_repositories(query)
    for repo in repos:
        stats["stars"] += repo.stargazers_count

    stats["followers"] = user.followers

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
    level = levels[min(lower_values)]
    g.close()
    return level


@app.route("/")
def index():
    username = request.args.get("user")
    if username:
        result = get_rank(username)
        return result
    else:
        abort(404)


if __name__ == "__main__":
    app.run(debug=True)
