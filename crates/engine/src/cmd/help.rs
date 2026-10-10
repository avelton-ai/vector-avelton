//! Help → community and project links (the Avelton Discord, website, this app's page and its
//! GitHub repository). The commands return the URL; the frontend opens it.

use serde_json::{Value, json};

use super::*;

/// The app's id on avelton.online and GitHub.
pub const APP_ID: &str = "vectorcraft";
pub const DISCORD_URL: &str = "https://github.com/avelton-ai/vector-avelton/issues";
pub const WEBSITE_URL: &str = "https://avelton.online";

/// This app's page on the website.
pub fn app_page_url() -> String {
    "https://vector.avelton.online".into()
}

/// This app's source repository.
pub fn github_url() -> String {
    "https://github.com/avelton-ai/vector-avelton".into()
}

pub fn specs() -> Vec<CommandSpec> {
    vec![
        cmd!(query "help.discord", "Avelton support", ["Help"], None, "{} → {url} Avelton support", always, |_, _| url(DISCORD_URL.into())),
        cmd!(query "help.website", "Avelton Website", ["Help"], None, "{} → {url}", always, |_, _| url(WEBSITE_URL.into())),
        cmd!(query "help.appPage", "Vector Avelton on avelton.online", ["Help"], None, "{} → {url} this app's page", always, |_, _| url(app_page_url())),
        cmd!(query "help.github", "Vector Avelton on GitHub", ["Help"], None, "{} → {url} source code, issues and releases", always, |_, _| url(github_url())),
        cmd!(query "help.links", "Links", [], None, "{} → {discord, website, appPage, github}", always, |_, _| {
            Ok(json!({ "discord": DISCORD_URL, "website": WEBSITE_URL, "appPage": app_page_url(), "github": github_url() }))
        }),
    ]
}

fn url(u: String) -> Result<Value> {
    Ok(json!({ "url": u }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn links() {
        let mut s = Session::new();
        assert_eq!(s.execute("help.discord", &json!({})).unwrap()["url"], "https://github.com/avelton-ai/vector-avelton/issues");
        assert_eq!(s.execute("help.appPage", &json!({})).unwrap()["url"], "https://vector.avelton.online");
        assert_eq!(s.execute("help.github", &json!({})).unwrap()["url"], "https://github.com/avelton-ai/vector-avelton");
        assert_eq!(s.execute("help.links", &json!({})).unwrap()["website"], "https://avelton.online");
    }
}
