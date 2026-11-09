// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title HeadcountRegistry
/// @notice Append-only record of Headcount report fingerprints, one per UTC day.
/// @dev A fingerprint is SHA-256 over a snapshot's row files (see headcount/snapshot.py).
///      Once a day is published it can never be changed, so a report cannot be
///      quietly edited after the fact: anyone can recompute the digest and call verify.
contract HeadcountRegistry {
    struct Snapshot {
        bytes32 digest;
        uint64 publishedAt;
    }

    address public owner;
    address public pendingOwner;
    /// @notice The newest day published, as YYYYMMDD.
    uint32 public latestDay;

    mapping(uint32 day => Snapshot) private _snapshots;

    event SnapshotPublished(uint32 indexed day, bytes32 digest, string uri);
    event OwnershipTransferStarted(address indexed previousOwner, address indexed newOwner);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    error NotOwner();
    error NotPendingOwner();
    error ZeroAddress();
    error InvalidDay(uint32 day);
    error EmptyDigest();
    error AlreadyPublished(uint32 day);

    modifier onlyOwner() {
        _checkOwner();
        _;
    }

    constructor(address initialOwner) {
        if (initialOwner == address(0)) revert ZeroAddress();
        owner = initialOwner;
        emit OwnershipTransferred(address(0), initialOwner);
    }

    /// @notice Record the fingerprint of one day's report.
    /// @param day The UTC date the scan window ends on, as YYYYMMDD.
    /// @param digest SHA-256 over the snapshot's row files.
    /// @param uri Where the snapshot files can be read, for anyone checking the digest.
    function publish(uint32 day, bytes32 digest, string calldata uri) external onlyOwner {
        if (!isValidDay(day)) revert InvalidDay(day);
        if (digest == bytes32(0)) revert EmptyDigest();
        if (_snapshots[day].publishedAt != 0) revert AlreadyPublished(day);

        _snapshots[day] = Snapshot({digest: digest, publishedAt: uint64(block.timestamp)});
        if (day > latestDay) latestDay = day;
        emit SnapshotPublished(day, digest, uri);
    }

    /// @notice The fingerprint recorded for a day, or zeros if none was published.
    function snapshotOf(uint32 day) external view returns (bytes32 digest, uint64 publishedAt) {
        Snapshot memory s = _snapshots[day];
        return (s.digest, s.publishedAt);
    }

    /// @notice True when `digest` is the fingerprint recorded for `day`.
    function verify(uint32 day, bytes32 digest) external view returns (bool) {
        return digest != bytes32(0) && _snapshots[day].digest == digest;
    }

    /// @notice A loose calendar check: year 2024-2999, month 1-12, day 1-31.
    function isValidDay(uint32 day) public pure returns (bool) {
        uint32 year = day / 10000;
        uint32 month = (day / 100) % 100;
        uint32 dom = day % 100;
        return year >= 2024 && year <= 2999 && month >= 1 && month <= 12 && dom >= 1 && dom <= 31;
    }

    /// @notice Start handing the registry to `newOwner`; they must call acceptOwnership.
    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        pendingOwner = newOwner;
        emit OwnershipTransferStarted(owner, newOwner);
    }

    function _checkOwner() internal view {
        if (msg.sender != owner) revert NotOwner();
    }

    function acceptOwnership() external {
        if (msg.sender != pendingOwner) revert NotPendingOwner();
        emit OwnershipTransferred(owner, msg.sender);
        owner = msg.sender;
        pendingOwner = address(0);
    }
}
