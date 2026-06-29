def test_agent_seed(client):
    response = client.get("/api/agents")

    assert response.status_code == 200
    agents = response.json()
    assert len(agents) == 7
    assert {agent["name"] for agent in agents} >= {
        "Financial Statement Agent",
        "News Catalyst Agent",
        "Technical Momentum Agent",
        "Risk Manager Agent",
        "Pump & Dump Risk Agent",
        "Skeptic Agent",
        "Chairman Agent",
    }

