#!/usr/bin/python

#
## mrlist
##
## This program provides an interface to read and manipulate Moira lists.
#

import common, ownership
import re, argparse, json, sys, datetime

import pymoira
from pymoira import List, ListMember, ListTracer

def resolve_member(name, default_to_string):
    """Resolve the list member name."""
    
    member = ListMember.resolveName(client, name)
    if member:
        return member
    
    if default_to_string:
        return ListMember( client, ListMember.String, name )
    else:
        return None

def output_member_list(members, hook = None):
    """Output the list of list members."""
    
    members = list(members)
    members.sort()
    type_headers = (
        ('USER', 'Users'),
        ('KERBEROS', 'Kerberos principals'),
        ('LIST', 'Sublists'),
        ('STRING', 'String entries (includes non-MIT emails)'),
        ('MACHINE', 'Machines'),
    )
    for list_type, header in type_headers:
        displayed = [member for member in members if member.mtype == list_type]
        if displayed:
            common.section_header(header)
            for member in displayed:
                if hasattr(member, 'tag') and member.tag:
                    print "* %s [%s]" % (member.name, member.tag)
                else:
                    print "* %s" % member.name
                if hook:
                    hook(member)
            print    # FIXME: this should not be done in case of last entry

def show_info():
    """Handle 'mrlist info'."""

    mlist = List(common.client, args.list)
    mlist.loadInfo()

    common.section_header("Information about list %s" % common.emph_text(mlist.name) )
    common.show_fields(
        ('Description', mlist.description),
        ('Active', mlist.active),
        ('Public', mlist.public),
        ('Visible', not mlist.hidden),
        ('Mailing list', mlist.is_mailing),
        ('AFS group', "GID #%s" % mlist.gid if mlist.is_afsgroup else mlist.is_afsgroup),
        ('Unix group', mlist.is_nfsgroup) if mlist.is_afsgroup else None,
        ('Mailman list', "On server %s" % mlist.mailman_server if mlist.is_mailman_list else mlist.is_mailman_list),
        ('Owner', str(mlist.owner) ),
        ('Membership ACL', str(mlist.memacl) if mlist.memacl else 'None' ),
        ('Last modified', "%s ago by %s using %s" % (common.last_modified_date(mlist.lastmod_datetime), mlist.lastmod_by, mlist.lastmod_with)),
    )

def show_inverse():
    """Handle 'mrlist inverse'."""

    member = resolve_member(args.member, False)
    if not member:
        print "Impossible to determine the type of a member. Please specify it explicitly by prefixing the member with type, seperated by colon, like this: string:test@example.com"
        return

    memberships = list( member.getMemberships(recursive = args.recursive) )
    memberships.sort()
    common.section_header( "Memberships of %s" % common.emph_text( str(member) ) )
    for mlist in memberships:
        print "* %s" % mlist.name

def show_members():
    """Handle 'mrlist members'."""

    mlist = List(common.client, args.list)
    members = mlist.getExplicitMembers(tags = args.verbose)
    output_member_list(members)

def expand_list():
    """Handle 'mrlist expand'."""
    
    mlist = List(common.client, args.list)
    if args.server_side:
        members = mlist.getAllMembers(server_side = True, include_lists = args.include_lists)
        if args.trace:
            print "Server-side tracing is not supported"
            return
    else:
        if args.trace:
            tracer = ListTracer(mlist)
            members = tracer.members
            inaccessible = tracer.inaccessible
            lists = tracer.lists

            # List tracer includes lists by default
            if not args.include_lists:
                    members = [member for member in members if member.mtype != ListMember.List]
        else:
            members, inaccessible, lists = mlist.getAllMembers(include_lists = args.include_lists)
        
        print "List %s contains %i members, found by expanding %i nested lists (access denied to %i)" % (mlist.name, len(members), len(lists), len(inaccessible))
    
    if args.trace:
        def show_trace(member):
            pathways = tracer.trace(member)
            if len(pathways) > 3 and not args.verbose:
                print "   [%i inclusion pathways]" % len(pathways)
            else:
                for pathway in pathways:
                    print "   - " + " -> ".join( pathway + (member.name,) )
        
        output_member_list(members, show_trace)
    else:
        output_member_list(members)

def show_ownerships():
    """Handle 'mrlist ownerships'."""

    mlist = List(client, args.list)
    ownership.show_ownerships(client, args, mlist)

def add_member():
    """Handle 'mrlist add'."""

    mlist = List(client, args.list)
    member = resolve_member(args.member, True)
    mlist.addMember(member)
    print "Added %s to list %s" % (common.emph_text( str(member) ), common.emph_text( mlist.name ))

def remove_member():
    """Handle 'mrlist remove'."""

    mlist = List(client, args.list)
    member = resolve_member(args.member, True)
    mlist.removeMember(member)
    print "Removed %s from list %s" % (common.emph_text( str(member) ), common.emph_text( mlist.name ))

    if args.reason:
        date = datetime.datetime.now().strftime("%d %b %Y")
        comment_params = (member.name.replace("@", " at "), args.reason, date, common.user_name())
        comment = "<devnull> %s removed due to %s %s (%s)" % comment_params
        commentholder = ListMember(client, ListMember.String, comment)
        mlist.addMember(commentholder)
        print "Added commment entry %s" % common.emph_text(comment)

def rename_list():
    """Handle 'mrlist rename'."""

    mlist = List(client, args.old_name)
    mlist.rename(args.new_name)
    print "Successfully renamed %s to %s" % (args.old_name, args.new_name)

def set_flags():
    """Handle 'mrlist set'."""

    mlist = List(client, args.list)

    valid_flags = ('active', 'inactive', 'public', 'private', 'visible', 'hidden', 'mailing', 'non-mailing', 'afs', 'non-afs', 'nfs', 'non-nfs')
    for flag in args.flag:
        if flag not in valid_flags:
            print "Invalid list flag: %s" % flag

    for flag in args.flag:
        if flag == 'active':
            mlist.setActiveFlag(True)
        if flag == 'inactive':
            mlist.setActiveFlag(False)
        if flag == 'public':
            mlist.setPublicFlag(True)
        if flag == 'private':
            mlist.setPublicFlag(False)
        if flag == 'visible':
            mlist.setHiddenFlag(False)
        if flag == 'hidden':
            mlist.setHiddenFlag(True)
        if flag == 'mailing':
            mlist.setMailingListFlag(True)
        if flag == 'non-mailing':
            mlist.setMailingListFlag(False)
        if flag == 'afs':
            mlist.setAFSGroupFlag(True)
        if flag == 'non-afs':
            mlist.setAFSGroupFlag(False)
        if flag == 'nfs':
            mlist.setNFSGroupFlag(True)
        if flag == 'non-nfs':
            mlist.setNFSGroupFlag(False)

def set_desc():
    """Handles 'mrlist setdesc'."""

    mlist = List(client, args.list)
    mlist.setDescription(args.description)

def set_owner():
    """Handles 'mrlist setowner'."""

    mlist = List(client, args.list)
    new_owner = resolve_member(args.owner, False)
    if not new_owner:
        raise UserError('Unable to determine owner type')

    mlist.setOwner(new_owner)
    print "Successfully changed owner of list %s to %s" % (common.emph_text(args.list), common.emph_text(str(new_owner)))

def set_memacl():
    """Handles 'mrlist setmemacl'."""

    mlist = List(client, args.list)
    if args.memacl.lower() == 'none':
        new_memacl = None
    else:
        new_memacl = resolve_member(args.memacl, False)
        if not new_memacl:
            print 'Unable to determine memacl type'
            return

    mlist.setMembershipACL(new_memacl)
    print "Successfully changed membership ACL of list %s to %s" % (common.emph_text(args.list), common.emph_text(str(new_memacl)))

def do_snapshot():
    """Handles 'mrlist snapshot'."""

    target_lists = set(args.list)
    if args.recursive:
        for listname in target_lists.copy():
            mlist = List(client, listname)
            all_members, denied, known = mlist.getAllMembers(include_lists = True)
            for member in all_members:
                if member.mtype == ListMember.List:
                    target_lists.add(member.name)

    dumps = {}
    for listname in target_lists:
        mlist = List(client, listname)
        try:
            dumps[listname] = mlist.serialize()
        except pymoira.MoiraError as err:
            common.error("Unable to backup list %s: %s" % (listname, err))
    json.dump(dumps, sys.stdout)

def setup_subcommands(argparser):
    """Sets up all the subcommands."""

    subparsers = argparser.add_subparsers()

    parser_add = subparsers.add_parser('add', help = 'Add a member to the list')
    parser_add.add_argument('list', help = 'The list to which the member will be added')
    parser_add.add_argument('member', help = 'The member to add to the list')

    parser_expand = subparsers.add_parser('expand', help = 'Recursively expands all sublists in the specified list')
    parser_expand.add_argument('list', help = 'The name of the list to show information about')
    parser_expand.add_argument('-l', '--include-lists', action = 'store_true', help = 'Display all the nested lists')
    parser_expand.add_argument('-s', '--server-side', action = 'store_true', help = argparse.SUPPRESS)    # for debug purposes
    parser_expand.add_argument('-t', '--trace', action = 'store_true', help = 'Show the paths through which the given user is included')
    parser_expand.add_argument('-v', '--verbose', action = 'store_true', help = 'Do not hide the inclusion pathways even if there are many of them')

    parser_info = subparsers.add_parser('info', help = 'Provide the information about the list')
    parser_info.add_argument('list', help = 'The list to inspect')

    parser_inverse = subparsers.add_parser('inverse', help = 'Show the lists into which certain member is included')
    parser_inverse.add_argument('member', help = 'The name of the member to show information about')
    parser_inverse.add_argument('-r', '--recursive', action = 'store_true', help = 'Show the lists into which a member is included through other lists')

    parser_members = subparsers.add_parser('members', help = 'Shows the members explicitly included into the list')
    parser_members.add_argument('list', help = 'The name of the list to show information about')
    parser_members.add_argument('-v', '--verbose', action = 'store_true', help = 'Output explicitly the members of the list')

    parser_ownerships = subparsers.add_parser('ownerships', help = 'Show items which this list owns')
    parser_ownerships.add_argument('list', help = 'The name of the list to show information about')
    parser_ownerships.add_argument('-r', '--recursive', action = 'store_true', help = 'Show items which this list own through being in other lists')

    parser_remove = subparsers.add_parser('remove', help = 'Remove a member from the list')
    parser_remove.add_argument('list', help = 'The list from which the member will be removed')
    parser_remove.add_argument('member', help = 'The member to remove from the list')
    parser_remove.add_argument('-r', '--reason', help = "Add a string entry exlaining the removal")

    parser_rename = subparsers.add_parser('rename', help = 'Rename a list')
    parser_rename.add_argument('old_name')
    parser_rename.add_argument('new_name')

    parser_set = subparsers.add_parser('set', help = 'Change list options')
    parser_set.add_argument('list', help = 'List to change the flags of')
    parser_set.add_argument('flag', nargs = '+', help = 'Flags to set')

    parser_setdesc = subparsers.add_parser('setdesc', help = 'Change the description of the list')
    parser_setdesc.add_argument('list', help = 'List to change the description of')
    parser_setdesc.add_argument('description', help = 'New list description')

    parser_setowner = subparsers.add_parser('setowner', help = 'Change the ownership of the list')
    parser_setowner.add_argument('list', help = 'List to change ownership of')
    parser_setowner.add_argument('owner', help = 'The new owner')

    parser_setmemacl = subparsers.add_parser('setmemacl', help = 'Change the membership ACL of the list')
    parser_setmemacl.add_argument('list', help = 'List to change membership of')
    parser_setmemacl.add_argument('memacl', help = 'New membership ACL')

    parser_snapshot = subparsers.add_parser('snapshot', help = 'Take a snapshot of the specified lists')
    parser_snapshot.add_argument('-r', '--recursive', action = 'store_true', help = 'Dump all lists nested into the specified lists')
    parser_snapshot.add_argument('list', nargs = '+', help = 'List to take the snapshot of')

    parser_add.set_defaults(handler = add_member)
    parser_expand.set_defaults(handler = expand_list)
    parser_info.set_defaults(handler = show_info)
    parser_inverse.set_defaults(handler = show_inverse)
    parser_members.set_defaults(handler = show_members)
    parser_ownerships.set_defaults(handler = show_ownerships)
    parser_remove.set_defaults(handler = remove_member)
    parser_rename.set_defaults(handler = rename_list)
    parser_set.set_defaults(handler = set_flags)
    parser_setdesc.set_defaults(handler = set_desc)
    parser_setowner.set_defaults(handler = set_owner)
    parser_setmemacl.set_defaults(handler = set_memacl)
    parser_snapshot.set_defaults(handler = do_snapshot)

    argparser.epilog = 'This mrlist has Super Cow Resistance'

if __name__ == '__main__':
    client, args = common.init('mrlist', 'Inspect and modify Moira lists', setup_subcommands)
    common.main()
