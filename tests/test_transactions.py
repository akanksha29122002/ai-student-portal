from datetime import date
from uuid import uuid4

import pytest

from app.domain.events import StudentRegistered
from app.infrastructure.repositories.memory import MemoryUnitOfWork
from app.schemas.core import BatchCreate, OrganizationCreate, StudentCreate
from app.services.store import InMemoryStore


def test_commit_persists_changes():
    store = InMemoryStore()
    uow = MemoryUnitOfWork(store)

    with uow:
        uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))

    assert len(store.organizations) == 1


def test_rollback_on_exception_reverts_all_changes():
    store = InMemoryStore()
    uow = MemoryUnitOfWork(store)

    with pytest.raises(RuntimeError):
        with uow:
            uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
            uow.organizations.create(OrganizationCreate(name="Acme", slug="acme"))
            raise RuntimeError("intentional failure")

    assert store.organizations == {}


def test_rollback_does_not_affect_prior_committed_transaction():
    store = InMemoryStore()
    uow = MemoryUnitOfWork(store)

    with uow:
        uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))

    with pytest.raises(ValueError):
        with uow:
            uow.organizations.create(OrganizationCreate(name="Acme", slug="acme"))
            raise ValueError("second transaction fails")

    assert len(store.organizations) == 1
    assert list(store.organizations.values())[0].slug == "kalvium"


def test_explicit_rollback_reverts_changes():
    store = InMemoryStore()
    uow = MemoryUnitOfWork(store)

    uow.__enter__()
    uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
    uow.rollback()
    uow.__exit__(None, None, None)

    assert store.organizations == {}


def test_explicit_commit_persists_changes():
    store = InMemoryStore()
    uow = MemoryUnitOfWork(store)

    uow.__enter__()
    uow.organizations.create(OrganizationCreate(name="Kalvium", slug="kalvium"))
    uow.commit()
    uow.__exit__(None, None, None)

    assert len(store.organizations) == 1


def test_domain_events_rolled_back_with_transaction():
    store = InMemoryStore()
    uow = MemoryUnitOfWork(store)
    agg_id = uuid4()

    with pytest.raises(RuntimeError):
        with uow:
            uow.events.append(StudentRegistered(aggregate_id=agg_id, payload={}))
            raise RuntimeError("force rollback")

    assert uow.events.list_by_aggregate(agg_id) == []


def test_domain_events_committed_with_transaction():
    store = InMemoryStore()
    uow = MemoryUnitOfWork(store)
    agg_id = uuid4()

    with uow:
        uow.events.append(StudentRegistered(aggregate_id=agg_id, payload={}))

    assert len(uow.events.list_by_aggregate(agg_id)) == 1


def test_nested_unit_of_work_is_independent():
    store = InMemoryStore()
    outer = MemoryUnitOfWork(store)
    nested = outer.begin_nested()

    with outer:
        outer.organizations.create(OrganizationCreate(name="Outer Org", slug="outer-org"))
        with pytest.raises(ValueError):
            with nested:
                nested.organizations.create(OrganizationCreate(name="Inner Org", slug="inner-org"))
                raise ValueError("nested fails")

    assert len(store.organizations) == 1
    assert list(store.organizations.values())[0].slug == "outer-org"


def test_multiple_transactions_accumulate_state():
    store = InMemoryStore()
    uow = MemoryUnitOfWork(store)

    with uow:
        uow.organizations.create(OrganizationCreate(name="Org A", slug="org-a"))

    with uow:
        uow.organizations.create(OrganizationCreate(name="Org B", slug="org-b"))

    assert len(store.organizations) == 2
