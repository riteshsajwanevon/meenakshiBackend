def test_lists_all_departments_with_their_documents(client, operator_headers):
    response = client.get("/api/v1/master-data/documents", headers=operator_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Master list of Document"
    assert [(d["code"], d["name"], len(d["documents"])) for d in data["departments"]] == [
        ("BOP", "BOP", 4),
        ("PRESS_SHOP", "Press shop", 3),
        ("WELD_SHOP", "Weld shop", 5),
        ("PLATING_POWDER_COATING_MIS", "Plating & Powder coating MIS", 6),
        ("PDI", "PDI", 6),
    ]
    all_documents = [doc for d in data["departments"] for doc in d["documents"]]
    assert [doc["sNo"] for doc in all_documents] == list(range(1, 25))
    assert all_documents[0] == {"sNo": 1, "code": "SUPPLIER_REJECTION_REPORT", "name": "Supplier rejection report"}


def test_one_department_case_insensitive(client, operator_headers):
    weld = client.get("/api/v1/master-data/documents/weld_shop", headers=operator_headers).json()
    assert [doc["name"] for doc in weld["documents"]] == [
        "Daily St. pass monitoring sheet", "Monthly St. pass monitoring sheet", "Daily or Monthly MIS", "Scrap note", "Pareto chart",
    ]


def test_unknown_department_and_auth(client, operator_headers):
    assert client.get("/api/v1/master-data/documents/PAINT", headers=operator_headers).status_code == 404
    assert client.get("/api/v1/master-data/documents").status_code == 401
