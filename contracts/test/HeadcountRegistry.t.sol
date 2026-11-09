// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {HeadcountRegistry} from "../src/HeadcountRegistry.sol";

contract HeadcountRegistryTest is Test {
    HeadcountRegistry internal registry;
    address internal owner = makeAddr("owner");
    address internal stranger = makeAddr("stranger");

    uint32 internal constant DAY = 20261107;
    bytes32 internal constant DIGEST = 0xa0b6c48471eb476488971dd04040dc42845c989e4436cb2a6d3dc806080a16d6;
    string internal constant URI = "https://github.com/Saber1Y/headcount/tree/main/snapshots/2026-11-07";

    event SnapshotPublished(uint32 indexed day, bytes32 digest, string uri);

    function setUp() public {
        registry = new HeadcountRegistry(owner);
    }

    function test_ConstructorRejectsZeroOwner() public {
        vm.expectRevert(HeadcountRegistry.ZeroAddress.selector);
        new HeadcountRegistry(address(0));
    }

    function test_PublishRecordsDigestTimeAndLatestDay() public {
        vm.warp(1_793_000_000);
        vm.expectEmit(true, false, false, true, address(registry));
        emit SnapshotPublished(DAY, DIGEST, URI);
        vm.prank(owner);
        registry.publish(DAY, DIGEST, URI);

        (bytes32 digest, uint64 publishedAt) = registry.snapshotOf(DAY);
        assertEq(digest, DIGEST);
        assertEq(publishedAt, 1_793_000_000);
        assertEq(registry.latestDay(), DAY);
        assertTrue(registry.verify(DAY, DIGEST));
    }

    function test_OnlyOwnerCanPublish() public {
        vm.expectRevert(HeadcountRegistry.NotOwner.selector);
        vm.prank(stranger);
        registry.publish(DAY, DIGEST, URI);
    }

    function test_DayCannotBeOverwritten() public {
        vm.startPrank(owner);
        registry.publish(DAY, DIGEST, URI);
        vm.expectRevert(abi.encodeWithSelector(HeadcountRegistry.AlreadyPublished.selector, DAY));
        registry.publish(DAY, keccak256("edited"), URI);
        vm.stopPrank();
        (bytes32 digest,) = registry.snapshotOf(DAY);
        assertEq(digest, DIGEST);
    }

    function test_EmptyDigestIsRejected() public {
        vm.expectRevert(HeadcountRegistry.EmptyDigest.selector);
        vm.prank(owner);
        registry.publish(DAY, bytes32(0), URI);
    }

    function test_InvalidDaysAreRejected() public {
        uint32[5] memory bad = [uint32(20231231), 20261301, 20261100, 20261132, 0];
        for (uint256 i; i < bad.length; ++i) {
            vm.expectRevert(abi.encodeWithSelector(HeadcountRegistry.InvalidDay.selector, bad[i]));
            vm.prank(owner);
            registry.publish(bad[i], DIGEST, URI);
        }
    }

    function test_LatestDayOnlyMovesForward() public {
        vm.startPrank(owner);
        registry.publish(20261109, DIGEST, URI);
        registry.publish(20261108, keccak256("b"), URI);
        vm.stopPrank();
        assertEq(registry.latestDay(), 20261109);
    }

    function test_VerifyRejectsWrongDigestUnknownDayAndZero() public {
        vm.prank(owner);
        registry.publish(DAY, DIGEST, URI);
        assertFalse(registry.verify(DAY, keccak256("other")));
        assertFalse(registry.verify(20261108, DIGEST));
        assertFalse(registry.verify(20261108, bytes32(0)));
    }

    function test_OwnershipTransferIsTwoStep() public {
        vm.prank(owner);
        registry.transferOwnership(stranger);
        assertEq(registry.owner(), owner);
        assertEq(registry.pendingOwner(), stranger);

        vm.expectRevert(HeadcountRegistry.NotPendingOwner.selector);
        vm.prank(owner);
        registry.acceptOwnership();

        vm.prank(stranger);
        registry.acceptOwnership();
        assertEq(registry.owner(), stranger);
        assertEq(registry.pendingOwner(), address(0));

        vm.expectRevert(HeadcountRegistry.NotOwner.selector);
        vm.prank(owner);
        registry.publish(DAY, DIGEST, URI);
    }

    function test_TransferToZeroIsRejected() public {
        vm.expectRevert(HeadcountRegistry.ZeroAddress.selector);
        vm.prank(owner);
        registry.transferOwnership(address(0));
    }

    function testFuzz_VerifyMatchesOnlyThePublishedDigest(bytes32 published, bytes32 probe) public {
        vm.assume(published != bytes32(0));
        vm.prank(owner);
        registry.publish(DAY, published, URI);
        assertEq(registry.verify(DAY, probe), probe == published);
    }

    function testFuzz_IsValidDayMatchesCalendarBounds(uint32 day) public view {
        uint32 y = day / 10000;
        uint32 m = (day / 100) % 100;
        uint32 d = day % 100;
        bool expected = y >= 2024 && y <= 2999 && m >= 1 && m <= 12 && d >= 1 && d <= 31;
        assertEq(registry.isValidDay(day), expected);
    }
}
