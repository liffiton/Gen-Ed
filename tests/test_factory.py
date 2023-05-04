from codehelp import create_app


def test_config():
    '''Verify passing in test config works.'''
    # If we run this (without setting TESTING), then configure_app_base() will configure a logger, which will break logging for all *later* tests...
    #assert not create_app().testing

    assert create_app({'TESTING': True}).testing


def test_landing(client):
    '''Make sure we get the landing page from a basic root path request.'''
    response = client.get('/')
    assert b"CodeHelp is a tool that can help you while you code." in response.data
